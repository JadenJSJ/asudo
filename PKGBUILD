pkgname=asudo
pkgver=0.0.1
pkgrel=2
pkgdesc='Launch a command in a session-scoped sudo broker environment'
arch=('any')
url='https://github.com/jadenjsj/asudo'
license=('MIT')
depends=('bash' 'python' 'sudo')

package() {
  make -C "$startdir" DESTDIR="$pkgdir" PREFIX=/usr install
}
