# ModelOps

End-to-end LLM onboarding on OpenShift.

Sandbox: compliance scan → GPU plan → deploy → prompt_injection
(passthrough) → prompt_injection (DeBERTa) → OpenShift Q&A → teardown →
approval → staging deploy → GuideLLM benchmark → registry → optional MaaS.

```bash
# Logged in with oc, cluster-admin recommended:
./deploy-all.sh
./deploy-all.sh --skip-maas          # omit Models-as-a-Service
./deploy-all.sh --skip-maas --skip-build
```

Both security gates use the same labeled jailbreak vs benign set scored
through `POST /v1/guardrail/checks` on a live NemoGuardrails Service.

- `security-scan` — passthrough rails, min-accuracy 0 (baseline)
- `security-scan-guardrail` — DeBERTa rails, min-accuracy 0.80
- `openshift-qa-eval` — five static Red Hat OpenShift Q&A items, token F1 (edd-demo BYOP)
