import os
import board
import digitalio
import busio
import time
import random
import microcontroller
import binascii
import gc           # for memory status

# ------- Network config ----------------
import mdns
import socketpool
import wifi
import ipaddress        # for the static ip setting
from adafruit_httpserver.server     import Server
from adafruit_httpserver.request    import Request
from adafruit_httpserver.response   import Response
from adafruit_httpserver            import POST

# ======== Networking ====================
print(f"[BOOT] Starting Network ...{str(gc.mem_free())}")
print(f"MAC:{binascii.hexlify(wifi.radio.mac_address)}")
if f"{os.getenv('WIFI_MODE')}" == "AP":
    wifi.radio.start_ap(ssid=f"{os.getenv('WIFI_AP_SSID')}", password=f"{os.getenv('WIFI_AP_PSK')}")
    print(f"WiFi AP mode: {str(wifi.radio.ipv4_address_ap)}")
    host_address = str(wifi.radio.ipv4_address_ap)     # for STA mode 
elif f"{os.getenv('WIFI_MODE')}" == "STA":
    if f"{os.getenv('IP_NETWORK')}" == "STATIC":
        ipv4_addr= ipaddress.IPv4Address(f"{os.getenv('IPV4_ADDR')}")
        netmask = ipaddress.IPv4Address(f"{os.getenv('IPV4_NETMASK')}")
        gateway = ipaddress.IPv4Address(f"{os.getenv('IPV4_GATEWAY')}")
        wifi.radio.set_ipv4_address(ipv4=ipv4_addr, netmask=netmask, gateway=gateway)
    WIFI_SSID = f"{os.getenv('WIFI_STA_SSID')}"
    WIFI_PASS = f"{os.getenv('WIFI_STA_PASSWORD')}"
    print(f"Connecting to Wi-Fi \"{WIFI_SSID}\"...")
    wifi.radio.connect(WIFI_SSID, WIFI_PASS) # waits for IP address
    print(f"Assigned IP address = {wifi.radio.ipv4_address}")
    host_address = str(wifi.radio.ipv4_address)     # for STA mode 

# Starting mDNS broad casting
print(f"[BOOT] Starting mDNS ...{str(gc.mem_free())}")
mdns_server = mdns.Server(wifi.radio)   # Creating mDNS server obj
mdns_server.hostname = "esp32kt"        # Accessble with 'esp32kt.local'
mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=80)
print(f"mDNS name: {str(mdns_server.hostname)}.local")

# ======== HTTP server ====================
# -------- Route/Alias setting ------------
# -------- References ---------------------
#   https://docs.circuitpython.org/projects/httpserver/en/latest/
# -------- Stylesheets/JavaScript Templates ------------
#   https://getbootstrap.com/docs/5.3/getting-started/download/
#   MIME Types: https://docs.circuitpython.org/projects/httpserver/en/latest/api.html#adafruit_httpserver.mime_types.MIMETypes
#   HTTPD: https://learn.adafruit.com/pico-w-http-server-with-circuitpython/code-the-pico-w-http-server
#   CSS/JS:https://popper.js.org/
#   JS:    https://cdnjs.com/libraries/popper.js/2.11.8

print(f"[BOOT] Starting HTTPD ...{str(gc.mem_free())}")
document_root = "/www_root"

def webpage_conv(filename, root):
    filepath = f"{root}/{filename}"
    with open(filepath, 'r') as f:
        html = f.read()
    html = html.replace('$TEMP$', f'{microcontroller.cpu.temperature:.1f}')
    return html

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool)

@server.route("/")
def base_handler(request: Request):
    return Response(request, webpage_conv('index.html', document_root), content_type='text/html')
#def base_handler(request: Request):
#    with Response(request, content_type='text/html') as resp:
#        resp.send(webpage_conv('index.html', document_root))

@server.route("/", POST)
def buttonpress(request: POST):
    global last_color
    raw_text = request.raw_request.decode("utf8")
    #print(raw_text)
    last_color = None
    if "RED" in raw_text:
        print("RED")
    if "GREEN" in raw_text:
        print("GREEN")
    if "BLUE" in raw_text:
        print("BLUE")
    if "WHITE" in raw_text:
        print("WHITE")
    if "YELLOW" in raw_text:
        print("YELLOW")
    if "OFF" in raw_text:
        print("OFF")
    if last_color is not None:
        print("No last color")
    elif "RANDOM" in raw_text:
        print("RANDOM")

    return Response(request, webpage_conv('index.html', document_root), content_type='text/html')

@server.route("/hello")
def hello_handler(request: Request):  # pylint: disable=unused-argument
    return Response(request, "<html><head></head><body>HELLO WORLD.</body></html>", content_type='text/html')

@server.route("/cpu", append_slash=True)
def cpu_information_handler(request: Request):
    data = {
        "temperature": microcontroller.cpu.temperature,
        "frequency": microcontroller.cpu.frequency,
        "voltage": microcontroller.cpu.voltage,
    }
    data_html = "CPU Temp:"+str(data["temperature"])+" C"
    return Response(request, "<html><head></head><body>"+data_html+"</body></html>", content_type='text/html')

server.start(host=host_address, port=80)        # Starting HTTP server

print("[BOOT] DONE ...")
print("[APP ] READY.")

clock = time.monotonic() #  time.monotonic() holder for server ping
while True:
    try:# As main loop
        
        if (clock + 30) < time.monotonic():  #  every 30 seconds, ping server & update temp reading
            print(gc.mem_free())
            if f"{os.getenv('WIFI_MODE')}" == "STA":
                if wifi.radio.ping(wifi.radio.ipv4_gateway) is None:
                    print("[IPv4 status] Disconnected")
                else:
                    pass
                    #print("[IPv4 status] Active")
            clock = time.monotonic()
        server.poll()
    except OSError as error:
        print(error)
        continue



