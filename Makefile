.PHONY: dev test smoke eval build install

dev:
	node scripts/dev.mjs

install:
	npm --prefix frontend install

test:
	py -m unittest discover -s tests -t .

smoke:
	py -m backend.app.smoke

eval:
	py -m backend.app.eval_cli

build:
	npm --prefix frontend run build
