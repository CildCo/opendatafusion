.PHONY: test build e2e helm
PYTHON ?= python

test:
	cd impl && $(PYTHON) -m pytest -q

build:
	cd frontend && npm run build

e2e:
	cd frontend && npm run test:e2e

helm:
	helm lint deploy/helm/odf
	helm template odf deploy/helm/odf --set secrets.create=true \
	  --set-string secrets.databaseUrl='postgresql+psycopg://u:p@pg/odf' \
	  --set-string secrets.jwtSecret='test-only-jwt-secret-not-for-production' \
	  --set-string secrets.fernetKey='test-only-fernet-key-not-for-production' \
	  > /tmp/odf-rendered.yaml
