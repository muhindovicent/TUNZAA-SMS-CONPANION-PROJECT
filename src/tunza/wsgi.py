"""WSGI entry point for gunicorn."""

from tunza.app import create_app

app = create_app()
