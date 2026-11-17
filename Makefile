UV ?= uv
RUN = $(UV) run --locked

.PHONY: test coverage build clean

test:
	$(RUN) python -m unittest discover -s tests

coverage:
	$(RUN) python -m coverage run --source=hf_cache_sync -m unittest discover -s tests
	$(RUN) python -m coverage report --fail-under=80 -m

build:
	$(RUN) python -m PyInstaller --onefile --name hf-cache-sync --noconfirm hf_cache_sync_cli.py

clean:
	python3 -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('build', 'dist')]"

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
VERSION ?= 0.1.0

.PHONY: install deb appimage

install: build
	install -d "$(DESTDIR)$(BINDIR)"
	install -m 755 dist/hf-cache-sync "$(DESTDIR)$(BINDIR)/hf-cache-sync"

deb: build
	VERSION="$(VERSION)" sh packaging/build-deb.sh

appimage: build
	VERSION="$(VERSION)" sh packaging/build-appimage.sh

.PHONY: help

help:
	@printf '%s\n' \
	  'Available targets:' \
	  '  help      Show this help' \
	  '  test      Run the test suite' \
	  '  coverage  Run tests and enforce 80% coverage' \
	  '  build     Build the standalone executable' \
	  '  install   Build and install the executable' \
	  '  deb       Build the Debian package' \
	  '  appimage  Build the AppImage package' \
	  '  clean     Remove build and distribution directories' \
	  '' \
	  'Variables: UV, PREFIX, BINDIR, DESTDIR, VERSION'
