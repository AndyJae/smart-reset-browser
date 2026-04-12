"""UDP camera discovery — platform-independent, no UI dependencies."""

import ipaddress
import logging
import re
import socket
import subprocess
from typing import Optional


# ---------------------------------------------------------------------------
# IP helpers
# ---------------------------------------------------------------------------

def is_valid_ipv4(value: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(value)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast:
        return False
    return True


def ipv4_bytes_to_str(parts: list[int]) -> str:
    return ".".join(str(p) for p in parts)


def get_local_ipv4s() -> list[str]:
    """Return all usable local IPv4 addresses via multiple strategies."""
    ips: list[str] = []

    # Strategy 1: ipconfig output (Windows)
    try:
        output = subprocess.check_output(
            ["ipconfig"],
            text=True,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="ignore",
        )
        for cand in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", output):
            if is_valid_ipv4(cand) and cand not in ips:
                ips.append(cand)
    except (OSError, subprocess.SubprocessError):
        pass

    # Strategy 2: UDP connect trick
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        if ip and is_valid_ipv4(ip) and ip not in ips:
            ips.append(ip)
    except OSError:
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass

    # Strategy 3: getaddrinfo
    try:
        addrinfos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        addrinfos = []
    for family, _socktype, _proto, _canonname, sockaddr in addrinfos:
        if family != socket.AF_INET:
            continue
        cand = sockaddr[0]
        if is_valid_ipv4(cand) and cand not in ips:
            ips.append(cand)

    # Strategy 4: gethostbyname
    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        if host_ip and is_valid_ipv4(host_ip) and host_ip not in ips:
            ips.append(host_ip)
    except OSError:
        pass

    return ips


# ---------------------------------------------------------------------------
# Interface info (MAC + netmask via ipconfig /all)
# ---------------------------------------------------------------------------

def _parse_ipconfig_interface_info(output: str, target_ips: set[str]) -> dict[str, dict[str, str]]:
    ipv4_regex = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
    mac_regex = re.compile(r"([0-9A-Fa-f]{2}(?:[-:][0-9A-Fa-f]{2}){5})")
    mask_regex = re.compile(
        r"\b(?:255|254|252|248|240|224|192|128|0)"
        r"\.(?:255|254|252|248|240|224|192|128|0)"
        r"\.(?:255|254|252|248|240|224|192|128|0)"
        r"\.(?:255|254|252|248|240|224|192|128|0)\b"
    )

    info: dict[str, dict[str, str]] = {}
    current_ips: list[str] = []
    current_mac: Optional[str] = None
    current_mask: Optional[str] = None

    def _flush():
        if not current_ips:
            return
        for current_ip in current_ips:
            if current_ip not in target_ips:
                continue
            entry = info.setdefault(current_ip, {})
            if current_mac:
                entry["mac"] = current_mac
            if current_mask:
                entry["netmask"] = current_mask

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            _flush()
            current_ips = []
            current_mac = None
            current_mask = None
            continue
        mac_match = mac_regex.search(line)
        if mac_match:
            current_mac = mac_match.group(1)
        for ip_match in ipv4_regex.findall(line):
            if ip_match not in current_ips:
                current_ips.append(ip_match)
        mask_match = mask_regex.search(line)
        if mask_match:
            current_mask = mask_match.group(0)

    _flush()
    return info


def get_ipconfig_interface_info(target_ips: list[str]) -> dict[str, dict[str, str]]:
    try:
        output = subprocess.check_output(
            ["ipconfig", "/all"],
            text=True,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="ignore",
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    return _parse_ipconfig_interface_info(output, set(target_ips))


def _calc_broadcast_addr(ip: str, netmask: Optional[str] = None) -> str:
    try:
        network = ipaddress.ip_network(
            f"{ip}/{netmask}" if netmask else f"{ip}/24", strict=False
        )
    except ValueError:
        return "255.255.255.255"
    return str(network.broadcast_address)


def _get_source_mac(ip: Optional[str], mac_text: Optional[str] = None) -> list[int]:
    if mac_text:
        try:
            return [int(p, 16) for p in mac_text.replace("-", ":").split(":")]
        except ValueError:
            pass
    return [2, 0, 0, 0, 0, 0]


# ---------------------------------------------------------------------------
# Discovery packet construction + parsing (Panasonic protocol)
# ---------------------------------------------------------------------------

def _build_discovery_request(source_mac: list[int], source_ip: list[int]) -> bytes:
    return bytes([
        0x00, 0x01, 0x00, 0x2A, 0x00, 0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        source_mac[0], source_mac[1], source_mac[2],
        source_mac[3], source_mac[4], source_mac[5],
        source_ip[0], source_ip[1], source_ip[2], source_ip[3],
        0x00, 0x00, 0x20, 0x11, 0x1E, 0x11, 0x23, 0x1F, 0x1E, 0x19, 0x13,
        0x00, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xF0,
        0x00, 0x26, 0x00, 0x20, 0x00, 0x21, 0x00, 0x22, 0x00, 0x23, 0x00, 0x25, 0x00, 0x28,
        0x00, 0x40, 0x00, 0x41, 0x00, 0x42, 0x00, 0x44, 0x00, 0xA5, 0x00, 0xA6, 0x00, 0xA7,
        0x00, 0xA8, 0x00, 0xAD, 0x00, 0xB3, 0x00, 0xB4, 0x00, 0xB7, 0x00, 0xB8,
        0xFF, 0xFF, 0x12, 0x21,
    ])


def _parse_camera_configuration(datagram: bytes) -> Optional[dict]:
    if len(datagram) <= 58:
        return None

    def _index_map(data: bytes) -> dict[int, slice]:
        idx: dict[int, slice] = {}
        cursor = 58
        while cursor < len(data) - 4:
            length = (data[cursor + 2] << 8) + data[cursor + 3]
            field_id = (data[cursor] << 8) + data[cursor + 1]
            start = cursor + 4
            end = start + length
            if end > len(data):
                break
            idx[field_id] = slice(start, end)
            cursor += length + 4
        return idx

    def _get(field_id: int) -> Optional[bytes]:
        s = index.get(field_id)
        return datagram[s] if s else None

    def _double_check(primary: int, alternate: int) -> Optional[bytes]:
        a, b = _get(primary), _get(alternate)
        if a is None or b is None or a != b:
            return None
        return a

    def _decode_c_string(raw: bytes) -> str:
        try:
            raw = raw[: raw.index(0)]
        except ValueError:
            pass
        return raw.decode("utf-8", errors="ignore")

    index = _index_map(datagram)
    mac = list(datagram[6:12])

    ip_slice       = _double_check(0x20, 0xA0)
    netmask_slice  = _double_check(0x21, 0xA1)
    gateway_slice  = _double_check(0x22, 0xA2)
    dns_slice      = _get(0x23)
    port_slice     = _double_check(0x25, 0x44)
    model_slice    = _get(0xA8)
    name_slice     = _get(0xA7)

    if not all([ip_slice, netmask_slice, gateway_slice, dns_slice, port_slice, model_slice, name_slice]):
        return None

    port = (port_slice[0] << 8) + port_slice[1]

    return {
        "mac":           mac,
        "ip":            list(ip_slice),
        "netmask":       list(netmask_slice),
        "gateway":       list(gateway_slice),
        "dns_primary":   list(dns_slice[:4]),
        "dns_secondary": list(dns_slice[4:8]),
        "port":          port,
        "model":         _decode_c_string(model_slice),
        "name":          _decode_c_string(name_slice),
    }


# ---------------------------------------------------------------------------
# Socket lifecycle
# ---------------------------------------------------------------------------

def create_discovery_socket() -> Optional[socket.socket]:
    """Create and bind the UDP socket used for discovery. Returns None on failure."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        pass
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    try:
        sock.bind(("", 10669))
    except OSError:
        try:
            sock.bind(("", 0))
        except OSError:
            sock.close()
            logging.error("Discovery socket bind failed.")
            return None
    return sock


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def discover_cameras(sock: socket.socket) -> list[dict]:
    """
    Send UDP discovery broadcast and collect camera responses.

    Returns a list of camera config dicts, each with keys:
      mac, ip (list[int]), port, model, name, netmask, gateway,
      dns_primary, dns_secondary.

    Caller owns the socket lifecycle (create / close).
    """
    local_ips = get_local_ipv4s()
    if not local_ips:
        logging.info("Network scan aborted: no local IPv4 address found.")
        return []

    ipconfig_info = get_ipconfig_interface_info(local_ips)

    target_packets: dict[str, bytes] = {}
    for ip in local_ips:
        try:
            parts = [int(o) for o in ipaddress.IPv4Address(ip).packed]
        except (ValueError, ipaddress.AddressValueError):
            continue
        info = ipconfig_info.get(ip, {})
        broadcast = _calc_broadcast_addr(ip, info.get("netmask"))
        mac = _get_source_mac(ip, info.get("mac"))
        packet = _build_discovery_request(mac, parts)
        target_packets.setdefault(broadcast, packet)
        target_packets.setdefault("255.255.255.255", packet)

    if not target_packets:
        logging.info("Network scan aborted: no valid local IPv4 address found.")
        return []

    configs: list[dict] = []
    seen: set[tuple] = set()

    try:
        sock.settimeout(0.3)

        # Flush stale datagrams.
        while True:
            try:
                sock.recvfrom(4096)
            except (socket.timeout, OSError):
                break

        for broadcast_addr, packet in target_packets.items():
            try:
                sock.sendto(packet, (broadcast_addr, 10670))
            except OSError:
                continue

        import time
        deadline = time.time() + 2.5
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            if len(data) < 4 or data[:4] != b"\x00\x01\x01\x75":
                continue
            config = _parse_camera_configuration(data)
            if not config:
                continue
            key = tuple(config["mac"])
            if key in seen:
                continue
            seen.add(key)
            configs.append(config)

    except OSError as exc:
        logging.error(f"Discovery socket error: {exc}")
        return []

    return configs


def format_discovered_cameras(configs: list[dict]) -> list[dict]:
    """
    Convert raw config dicts to the format used by the UI / API:
      [{"label": "AW-UE160 (192.168.0.10:80)", "model": ..., "ip": ..., "port": ...}]
    """
    result = []
    for config in configs:
        model = config.get("model") or "Camera"
        ip = ipv4_bytes_to_str(config.get("ip", []))
        port = config.get("port", 80)
        if ip:
            result.append({
                "label": f"{model} ({ip}:{port})",
                "model": model,
                "ip": ip,
                "port": str(port),
            })
    return result
