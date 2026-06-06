"""
ML service interface layer.

These modules are the thin shims the Django side calls into. They either run
inference locally using artifacts in `ml_services/artifacts/`, or proxy to a
FastAPI microservice at `settings.ML_SERVICE_URL` via httpx. Ahad fills the
real logic.
"""
