.PHONY: release

release:
	@if [ -z "$(version)" ]; then \
		echo "Please specify version: e.g, make release version=v0.0.6"; \
		exit 1; \
	fi
	@echo "Updating version to $(version:v%=%)"
	@python -c 'import tomli; import tomli_w; \
		data = tomli.load(open("pyproject.toml", "rb")); \
		data["project"]["version"] = "$(version:v%=%)"; \
		tomli_w.dump(data, open("pyproject.toml", "wb"))'
	@python -c 'open("src/version.py", "w").write("__version__ = \"$(version:v%=%)\"\n")'
	@python -c 'import json; \
		data = json.load(open("server.json", "r")); \
		data["version"] = "$(version:v%=%)"; \
		data["packages"][0]["version"] = "$(version:v%=%)"; \
		json.dump(data, open("server.json", "w"), indent=2)'
	@uv sync
	@git add .
	@git commit -m "release: update version to $(version:v%=%)"
	@git push origin main
	@git tag $(version)
	@git push origin $(version)
	@echo "Version updated and tag pushed. GitHub Actions will handle the release."
