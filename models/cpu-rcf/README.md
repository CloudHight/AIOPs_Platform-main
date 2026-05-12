# CPU RCF

CPU Random Cut Forest model workflow.

Input contract:

- Content type: `text/csv`
- Payload: newline-separated CPU values
- Expected response: `{"scores":[{"score":0.0}]}`

Training remains in `../../RCF_Model/`. The wrapper `../../scripts/train_cpu_model.sh` runs the existing creation/training flow and stores metadata under `dist/modelops/cpu-rcf/`.
