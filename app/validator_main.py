from app.core.env import load_app_env

load_app_env()

from fastapi import FastAPI

from app.api.routes.audit_validator import router as audit_validator_router

validator_app = FastAPI(title="Audit Validator Service")
validator_app.include_router(audit_validator_router)
