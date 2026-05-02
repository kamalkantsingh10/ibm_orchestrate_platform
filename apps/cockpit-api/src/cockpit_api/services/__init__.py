"""Service layer — orchestration that does not touch SQL directly.

Routers depend on services; services depend on repositories. The router
layer never imports from ``repositories/`` directly.
"""
