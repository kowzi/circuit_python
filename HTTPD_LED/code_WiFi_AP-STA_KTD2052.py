import os
import board
import digitalio
import busio
import time
import random
import microcontroller
import binascii
import gc           # for memory status

# ------- App config
print("[BOOT] Starting App Setting ...")
#i2c = board.I2C()  # uses board.SCL and board.SDA
i2c = busio.I2C(board.SCL,board.SDA,frequency=400000)      #  Adafruit ESP32-S2 TFT Feather

def i2c_write(SID,regAddr,regData):
    msg = bytearray([regAddr,regData])
    i2c.writeto(SID,msg)
def i2c_read(SID,regAddr):
    msg = bytearray([regAddr])
    i2c.writeto(SID,msg)
    result = bytearray(1)
    i2c.readfrom_into(SID,result)
    return bin(result[0])

SID2 = 0x74  # 7-bit slave addresses on i2c bus, KTD2052=0x74, untrimmed=0x60

rmax = 64  # 64/8 = 8mA
gmax = 64  # 64/8 = 8mA
bmax = 80  # 80/8 = 10mA
en_mode = 2  # EnableMode:   1=night, 2=normal(day)
be_en = 1    # BrightExtend: 0=disabled, 1=enabled
ce_temp = 2  # CoolExtend:   0=135C, 1=120C, 2=105C, 3=90C
on = en_mode*64 + be_en*32 + ce_temp*8          # calculate global on
off = be_en*32 + ce_temp*8                      # calculate global off
rgb_list = [1,2,3,4]
fade_list = [0.032, 0.063, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
alpha = 0.04045
phi = 12.92
gamma = 2.4
red_list = [0]
grn_list = [0]
blu_list = [0]
for i in range(1, 24, 1):
    red_list.append(round(((i/255.0)/phi)*rmax))
    grn_list.append(round(((i/255.0)/phi)*gmax))
    blu_list.append(round(((i/255.0)/phi)*bmax))
for i in range(24, 256, 1):
    red_list.append(round(pow((i/255.0 + alpha)/(1 + alpha), gamma)*rmax))
    grn_list.append(round(pow((i/255.0 + alpha)/(1 + alpha), gamma)*gmax))
    blu_list.append(round(pow((i/255.0 + alpha)/(1 + alpha), gamma)*bmax))

gc.collect()

# Core Functions ################################
def global_on(fade0):
    i2c_write(SID2,0x02,on+fade0)
def global_off(fade0):
    i2c_write(SID2,0x02,off+fade0)
def global_reset():
    i2c_write(SID2,0x02,0xC0)
def fade_off():
    global_off(2)  # fade0=2
    pattern_ctrl(0,0,0)  # turn pattern generator off
def color_rgbn(rgbn,r,g,b):  # rgbn = 1, 2, 3 or 4
    regAddr = 3*rgbn
    i2c_write(SID2,regAddr,red_list[r])
    i2c_write(SID2,regAddr+1,grn_list[g])
    i2c_write(SID2,regAddr+2,blu_list[b])
def color_all(r,g,b):
    for rgbn in rgb_list:
        color_rgbn(rgbn,r,g,b)
def color_rgbn_random(rgbn):  # rgbn = 1, 2, 3 or 4
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    color_rgbn(rgbn,r,g,b)
def color_all_random():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    color_all(r,g,b)
def pattern_ctrl(pg_mode,pg_time,fade1):
    # pg_mode:  0=off, 1=4slots, 2=6slots, 3=8slots
    # pg_time:  0=188ms, 1=250ms, 2=375ms, 3=500ms, 4=750ms, 5=1s, 6=1.5s, 7=2s per slots
    # fade1: 0=31ms, 1=63ms, 2=125ms, 3=250ms, 4=500ms, 5=1s, 6=2s, 7=4s exponential time constant
    regData = 64*pg_mode + 8*pg_time + fade1
    i2c_write(SID2,0x0F,regData)
def pattern_fade(regData):
    # use binary for regData (e.g. 0b00011111)
    i2c_write(SID2,0x10,regData)
def pattern_rgbn(rgbn,regData):
    # rgbn = 1, 2, 3 or 4
    # use binary for regData (e.g. 0b00011111)
    i2c_write(SID2,0x10+rgbn,regData)
def pattern_all(regData):
    # use binary for regData (e.g. 0b00011111)
    for rgbn in rgb_list:
        pattern_rgbn(rgbn,regData)
def pattern_watchdog(cycles):
    i2c_write(SID2,0x15,cycles)
    i2c_write(SID2,0x15,cycles)

# Library Functions #############################
def PowerUp_Boot_Sequence():  # example code that doesn't use pattern generator
    global_reset()
    color_rgbn(1,255,0,0)  # rgb1=red
    for i in range(3):  # flash RGB1 3 times
        global_on(0)
        time.sleep(0.05)
        global_off(0)
        time.sleep(0.2)
    time.sleep(0.2)
    global_reset()
    global_on(0)
    for i in range(1,5,1):  # chase white 1 time across all 4 RGBs
        color_rgbn(i,127,127,127)
        time.sleep(0.05)
        color_rgbn(i,0,0,0)
    time.sleep(1)

def Breathe_All_Blue(cycles):  # Breathe all RGBs Blue at 4s/cycle
    # Same color, fades and timing as AutoBreathe(TM) version.
    fade_off()
    color_all(0,0,255)  # all dim blue (10mA)
    pattern_ctrl(3,3,7)  # pg_mode=3 (8 pattern slots), pg_time=3 (500ms), fade1=7
    pattern_fade(0b00000111)
    pattern_all(0b00000111)
    pattern_watchdog(cycles)  # turn off after n cycles at 4s/cycle, or until interrupted
    global_on(4)  # fade0=4

def Google_Colors():
    # From quick web search; various differing results were found.
    color_rgbn(1,66,133,244)
    color_rgbn(2,234,67,53)
    color_rgbn(3,251,188,5)
    color_rgbn(4,52,168,83)

def Breathe_Google(cycles):  # Breathe Google Colors at 3s/cycle
    fade_off()
    Google_Colors()
    pattern_ctrl(3,2,7)  # pg_mode=3 (8 pattern slots), pg_time=2 (375ms), fade1=7
    pattern_fade(0b00001111)
    pattern_all(0b00001111)
    pattern_watchdog(cycles)  # turn off after n cycles at 3s/cycle, or until interrupted
    global_on(3)  # fade0=3

def Charge_1():
    fade_off()
    color_all(255,191,0)  # all amber
    pattern_ctrl(3,0,4)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=4
    pattern_fade(0b00011110)
    pattern_rgbn(1,0b00011110)
    pattern_rgbn(2,0b00000000)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(255)  # run forever until interrupted
    global_on(2)  # fade0=2

def Charge_2():
    fade_off()
    color_all(255,191,0)  # all amber
    pattern_ctrl(3,0,4)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=4
    pattern_fade(0b00011110)
    pattern_rgbn(1,0b11111111)
    pattern_rgbn(2,0b00011110)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(255)  # run forever until interrupted
    global_on(2)  # fade0=2

def Charge_3():
    fade_off()
    color_all(255,191,0)  # all amber
    pattern_ctrl(3,0,4)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=4
    pattern_fade(0b00011110)
    pattern_rgbn(1,0b11111111)
    pattern_rgbn(2,0b11111111)
    pattern_rgbn(3,0b00011110)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(255)  # run forever until interrupted
    global_on(2)  # fade0=2

def Charge_4():
    fade_off()
    color_all(255,191,0)  # all amber
    pattern_ctrl(3,0,4)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=4
    pattern_fade(0b00011110)
    pattern_rgbn(1,0b11111111)
    pattern_rgbn(2,0b11111111)
    pattern_rgbn(3,0b11111111)
    pattern_rgbn(4,0b00011110)
    pattern_watchdog(255)  # run forever until interrupted
    global_on(2)  # fade0=2

def Charge_Done():
    fade_off()
    color_all(0,255,0)  # all green
    global_on(4)  # fade0=4

def Power_Off(delay):                           # Fade all RGBs to off and go to low quiescent current standby
    fade_off()
    time.sleep(delay)
gc.collect()



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
#gc.collect()
#print(f"[BOOT] Starting mDNS ...{str(gc.mem_free())}")
#mdns_server = mdns.Server(wifi.radio)   # Creating mDNS server obj
#mdns_server.hostname = "esp32kt"        # Accessble with 'esp32kt.local'
#mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=80)
#print(f"mDNS name: {str(mdns_server.hostname)}.local")

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
flag_app = 0

@server.route("/")
def base_handler(request: Request):
    return Response(request, webpage_conv('index.html', document_root), content_type='text/html')
#def base_handler(request: Request):
#    with Response(request, content_type='text/html') as resp:
#        resp.send(webpage_conv('index.html', document_root))

@server.route("/", POST)
def buttonpress(request: POST):
    global last_color
    global flag_app
    raw_text = request.raw_request.decode("utf8")
    #print(raw_text)
    last_color = None
    if "RED" in raw_text:
        print("[HTTP POST] RED")
        flag_app = 1
    elif "GREEN" in raw_text:
        print("[HTTP POST] GREEN")
        flag_app = 2
    elif "BLUE" in raw_text:
        print("[HTTP POST] BLUE")
        flag_app = 3
    elif "WHITE" in raw_text:
        print("[HTTP POST] WHITE")
        flag_app = 4
    elif "YELLOW" in raw_text:
        print("[HTTP POST] YELLOW")
        flag_app = 5
    elif "OFF" in raw_text:
        print("[HTTP POST] OFF")
        flag_app = 6
    elif last_color is not None:
        print("No last color")
        flag_app = 0
    else:
        print("[HTTP POST] Unknown")
        flag_app = 6

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

while not i2c.try_lock():
    pass
Power_Off(2)
print("[BOOT] DONE ...")
print("[APP ] READY.")

#clock = time.monotonic() #  time.monotonic() holder for server ping
while True:
    try:# As main loop
        #if (clock + 30) < time.monotonic():  #  every 30 seconds, ping server & update temp reading
            #gc.collect()
            #print(f"[MEM FREE] {str(gc.mem_free())}")
            #if f"{os.getenv('WIFI_MODE')}" == "STA":
            #    if wifi.radio.ping(wifi.radio.ipv4_gateway) is None:
            #        print("[IPv4 status] Disconnected")
            #    else:
            #        pass
                    #print("[IPv4 status] Active")
            #clock = time.monotonic()
        
        # ATTN: DO-NOT-USE if-elif-else
        if flag_app == 1:
            PowerUp_Boot_Sequence()
        if flag_app == 2:
            Charge_2()
            #Breathe_All_Blue(4)
        if flag_app == 3:
            Charge_3()
            #Breathe_Google(2)
        if flag_app == 4:
            Charge_4()
        if flag_app == 5:
            Charge_Done()
        if flag_app == 6:
            Power_Off(1)

        flag_app = 0

        server.poll()
    except OSError as error:
        print(error)
        continue



