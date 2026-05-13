# secrets-manager

Secrets Manager resources converted from `AIOPs_SAM/template.yaml`.

Creates the Jira credentials secret shell only. Secret values must be populated out of band and must not be committed in Terraform files.

Use the default 30-day recovery window for shared and production environments. Ephemeral dev roots may set `recovery_window_in_days = 0` so repeated destroy/apply cycles do not leave a scheduled-deletion secret name that blocks the next pipeline run.
