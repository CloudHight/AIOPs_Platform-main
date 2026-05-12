# Nginx BERT

Nginx/log anomaly classifier workflow.

Input contract:

- Content type: `application/json`
- Payload: `{"inputs":"<normalized log line>"}`
- Expected response: list of label/score/threshold dictionaries

Training remains in `../../BERT_Model/`. The wrapper `../../scripts/train_log_model.sh` runs dataset creation and SageMaker tuning, then stores metadata under `dist/modelops/nginx-bert/`.
