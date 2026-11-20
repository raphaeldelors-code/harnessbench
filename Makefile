.PHONY: install lint build serve smoke validate bench-smoke

install:            ## set up dev tooling + pre-commit hooks
	python3 -m pip install -r requirements-dev.txt
	pre-commit install

lint:               ## run every hook over the whole tree
	pre-commit run --all-files

build:              ## rebuild the dashboard data
	python3 site/build.py

validate:           ## validate run manifests + data against schemas
	python3 tools/validate_data.py

serve:              ## serve the built dashboard locally
	python3 -m http.server 8088 --directory site/public

smoke:              ## headless browser checks (desktop + mobile)
	python3 tools/smoke.py

bench-smoke:        ## one toy-repo harness run against $HB_BACKEND_URL
	docker compose run --rm bench hb smoke --harness $(or $(HARNESS),mini)
