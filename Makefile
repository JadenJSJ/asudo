PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DOCDIR ?= $(PREFIX)/share/doc/asudo
LICENSEDIR ?= $(PREFIX)/share/licenses/asudo
LIBEXECDIR ?= $(PREFIX)/lib/asudo

.PHONY: install uninstall

install:
	install -Dm755 bin/asudo "$(DESTDIR)$(BINDIR)/asudo"
	install -Dm755 libexec/asudo-broker.py "$(DESTDIR)$(LIBEXECDIR)/asudo-broker.py"
	install -Dm755 libexec/asudo-sudo-client.py "$(DESTDIR)$(LIBEXECDIR)/asudo-sudo-client.py"
	install -Dm644 README.md "$(DESTDIR)$(DOCDIR)/README.md"
	install -Dm644 LICENSE "$(DESTDIR)$(LICENSEDIR)/LICENSE"

uninstall:
	rm -f "$(DESTDIR)$(BINDIR)/asudo"
	rm -f "$(DESTDIR)$(LIBEXECDIR)/asudo-broker.py"
	rm -f "$(DESTDIR)$(LIBEXECDIR)/asudo-sudo-client.py"
	rm -f "$(DESTDIR)$(DOCDIR)/README.md"
	rm -f "$(DESTDIR)$(LICENSEDIR)/LICENSE"
