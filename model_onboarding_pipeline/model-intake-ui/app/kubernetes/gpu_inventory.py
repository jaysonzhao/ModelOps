import logging
import time

from app.kubernetes.client import core_api

logger = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL_SECONDS = 20


def _ttl_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at <= time.monotonic():
        _CACHE.pop(key, None)
        return None
    return value


def _ttl_set(key, value, ttl=_CACHE_TTL_SECONDS):
    _CACHE[key] = (time.monotonic() + ttl, value)
    return value


def list_gpu_nodes():
    cached = _ttl_get("gpu_nodes")
    if cached is not None:
        return cached
    try:
        nodes = core_api().list_node(label_selector="nvidia.com/gpu.present=true")
        return _ttl_set("gpu_nodes", nodes.items)
    except Exception as exc:
        logger.warning("list_gpu_nodes failed: %s", exc)
        return []


def get_node(name):
    return core_api().read_node(name=name)


def list_gpu_pods(namespace=None):
    cache_key = ("gpu_pods", namespace or "*")
    cached = _ttl_get(cache_key)
    if cached is not None:
        return cached
    try:
        if namespace:
            pods = core_api().list_namespaced_pod(namespace=namespace)
        else:
            pods = core_api().list_pod_for_all_namespaces()
    except Exception as exc:
        logger.warning("list_gpu_pods failed: %s", exc)
        return []
    gpu_pods = []
    for pod in pods.items:
        for container in pod.spec.containers:
            reqs = (container.resources.requests or {})
            if "nvidia.com/gpu" in reqs:
                gpu_pods.append(pod)
                break
    return _ttl_set(cache_key, gpu_pods)


def parse_gpu_label_value(node, label_key, default="unknown"):
    return node.metadata.labels.get(label_key, default)


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_node_gpu_info(node):
    labels = node.metadata.labels or {}
    name = node.metadata.name
    status_capacity = node.status.capacity or {}
    status_allocatable = node.status.allocatable or {}

    schedulable_count = _as_int(status_allocatable.get("nvidia.com/gpu", 0))
    physical_count = _as_int(labels.get("nvidia.com/gpu.count"), schedulable_count or 1)
    gpu_product = labels.get("nvidia.com/gpu.product", "unknown")
    gpu_memory_mb = labels.get("nvidia.com/gpu.memory", "0")
    mig_enabled = labels.get("nvidia.com/mig.config", "")
    time_slicing_replicas = _as_int(labels.get("nvidia.com/gpu.replicas"), 1)
    is_shared = "-SHARED" in gpu_product or time_slicing_replicas > 1
    display_product = gpu_product.replace("-SHARED", "").replace("-", " ")

    return {
        "node_name": name,
        "gpu_count": schedulable_count,
        "physical_gpu_count": max(physical_count, 1),
        "schedulable_gpu_count": schedulable_count,
        "gpu_product": gpu_product,
        "display_product": display_product,
        "gpu_memory": gpu_memory_mb,
        "mig_enabled": bool(mig_enabled and mig_enabled not in ("", "all-disabled")),
        "mig_config": mig_enabled,
        "time_slicing_replicas": max(time_slicing_replicas, 1),
        "is_shared": is_shared,
        "node_ready": any(
            (c.type == "Ready" and c.status == "True")
            for c in (node.status.conditions or [])
        ),
    }
