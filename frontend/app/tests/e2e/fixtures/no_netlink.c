// LD_PRELOAD shim that fails NETLINK_ROUTE sockets with EAFNOSUPPORT, so
// Chromium's AddressTrackerLinux::Init takes its graceful "assume always
// online" path (the same path FreeBSD's Linuxulator triggers). This avoids
// netlink flake on CI runners where Docker/veth churn floods host netlink
// and causes ERR_NETWORK_CHANGED mid-navigation.
//
// Build: gcc -shared -fPIC -o no_netlink.so no_netlink.c -ldl
// Inject via Playwright launch env: {"LD_PRELOAD": "/path/to/no_netlink.so"}.

#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <linux/netlink.h>
#include <stddef.h>
#include <sys/socket.h>

int socket(int domain, int type, int protocol) {
    if (domain == AF_NETLINK && protocol == NETLINK_ROUTE) {
        errno = EAFNOSUPPORT;
        return -1;
    }
    static int (*real_socket)(int, int, int) = NULL;
    if (!real_socket) {
        real_socket = dlsym(RTLD_NEXT, "socket");
    }
    return real_socket(domain, type, protocol);
}
