import os
import socketpool
import wifi
from adafruit_httpserver import Server, Request, Response
WIFI_SSID = ""
WIFI_PASS = ""


print("Connecting to Wi-Fi \"{0}\"...".format(WIFI_SSID))
wifi.radio.connect(WIFI_SSID, WIFI_PASS) # waits for IP address
print("Connected, IP address = {0}".format(wifi.radio.ipv4_address))


import board
import digitalio
import busio
import time
import random

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

i2c = board.I2C()  # uses board.SCL and board.SDA
#i2c = busio.I2C(board.SCL1,board.SDA1,frequency=100000)
while not i2c.try_lock():
    pass

def i2c_write(SID,regAddr,regData):
    msg = bytearray([regAddr,regData])
    i2c.writeto(SID,msg)

def i2c_read(SID,regAddr):
    msg = bytearray([regAddr])
    i2c.writeto(SID,msg)
    result = bytearray(1)
    i2c.readfrom_into(SID,result)
    return bin(result[0])

#  *************************************************************************************************
#                                     Configure KTS1622
#  *************************************************************************************************
SID1 = 0x20                 # 7-bit slave addresses on i2c bus for the KTS1622. Other valid addresses (0x21, 0x22, and 0x23)
i2c_write(SID1, 0x06, 0x00) # Enables Port0 as output
i2c_write(SID1, 0x07, 0x00) # Enables Port1 as output
#  13)       Basic Light Patterns
#  Alternately flashes A0-A7 and B0-B7 LEDs using a nested for loop
def PatternCautionFlash(cycles):              #  13)  def PatternCautionFlash(cycles):
    for i in range(cycles):  #  loop range
        i2c_write(SID1, 0x02, 0b11111111)
        i2c_write(SID1, 0x03, 0b00000000)
        time.sleep(1)
        i2c_write(SID1, 0x02, 0b00000000)
        i2c_write(SID1, 0x03, 0b11111111)
        time.sleep(1)

#################################################
# Configuration #################################
#################################################

# RGB maximum current settings per LED Temperature Derating, Ipulse(max) & per
#   good White Color Balance or the Application's Brightness requirement.
#   The sRGB color coordinates will be scaled by the below maximums.
rmax = 64  # 64/8 = 8mA
gmax = 64  # 64/8 = 8mA
bmax = 80  # 80/8 = 10mA
# In this case, 8mA is by brightness choice, but blue is increased for balance.
#   Generally, the Everbright RGB can run as high as 15mA for red
#   and 16mA for green and blue indefinitly up to Ta=50C,
#   per the manufacturer's recommendations.

# i2c Addresses Configuration
SID2 = 0x74  # 7-bit slave addresses on i2c bus, KTD2052=0x74, untrimmed=0x60

# Control Mode Configuration
en_mode = 2  # EnableMode:   1=night, 2=normal(day)
be_en = 1    # BrightExtend: 0=disabled, 1=enabled
ce_temp = 2  # CoolExtend:   0=135C, 1=120C, 2=105C, 3=90C

# Calculations
on = en_mode*64 + be_en*32 + ce_temp*8          # calculate global on
off = be_en*32 + ce_temp*8                      # calculate global off

# RGB list for several for-loops
#    Can be modified when using less than four RGBs
rgb_list = [1,2,3,4]

# fade-rate exponential time-constant list
fade_list = [0.032, 0.063, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]

# generate the scaled sRGB integer lists using floating-point precision
    # math is per sRGB description in Wikipedia
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

#################################################
# Core Functions ################################
#################################################

# Control Register Core Functions

def global_on(fade0):
    i2c_write(SID2,0x02,on+fade0)

def global_off(fade0):
    i2c_write(SID2,0x02,off+fade0)

def global_reset():
    i2c_write(SID2,0x02,0xC0)

def fade_off():
    global_off(2)  # fade0=2
    pattern_ctrl(0,0,0)  # turn pattern generator off

# Color Setting Registers Core Functions

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

# Pattern Generator Registers Core Functions

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
    # Cycles is number of cycles before watchdog times out.
    # You can periodically refresh the cycles before it times out.
    # When cycles times out, the chip fades to zero and goes to low current standby mode.
    # 255 disables watchdog and runs until pattern generator mode is turned off.
    # Note: always write to the watchdog register twice.
    i2c_write(SID2,0x15,cycles)
    i2c_write(SID2,0x15,cycles)

#################################################
# Library Functions #############################
#################################################

def Chip_Status_Check():
    global_reset()
    color_all(31,31,31)  # all dark white to detect short or open-LED via BE_STAT bit
    global_on(2)
    time.sleep(3)
    #print("")
    #print("ID register =   ",i2c_read(SID2,0x00),
    #"    <101=Kinetic; 00110=KTD2052A/C, 00111=KTD2052B/D>")
    #print("Monitor register = ",i2c_read(SID2,0x01),
    #"    <1=don't care; 0000=good, 1xxx=SC, x1xx=BE, xx1x=CE, xxx1=UV/OT>")
    #print("    SC and BE will indicate short-circuit and open-LED faults.")
    #print("")
    fade_off()

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
    # color_rgbn(1,23,107,239)
    # color_rgbn(2,255,62,48)
    # color_rgbn(3,247,181,41)
    # color_rgbn(4,23,156,82)

def Breathe_Google(cycles):  # Breathe Google Colors at 3s/cycle
    fade_off()
    Google_Colors()
    pattern_ctrl(3,2,7)  # pg_mode=3 (8 pattern slots), pg_time=2 (375ms), fade1=7
    pattern_fade(0b00001111)
    pattern_all(0b00001111)
    pattern_watchdog(cycles)  # turn off after n cycles at 3s/cycle, or until interrupted
    global_on(3)  # fade0=3

def Fuel_4():
    fade_off()
    color_all(127,127,127)  # all white low-brightness
    pattern_ctrl(3,5,5)  # pg_mode=3 (8 pattern slots), pg_time=5 (1s), fade1=5
    pattern_fade(0b00000111)
    pattern_all(0b00000111)
    pattern_watchdog(1)  # run 1 time
    global_on(2)  # fade0=2

def Fuel_3():
    fade_off()
    color_all(127,127,127)  # all white low-brightness
    pattern_ctrl(3,5,5)  # pg_mode=3 (8 pattern slots), pg_time=5 (1s), fade1=5
    pattern_fade(0b00000111)
    pattern_rgbn(1,0b00000111)
    pattern_rgbn(2,0b00000111)
    pattern_rgbn(3,0b00000111)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(1)  # run 1 time
    global_on(2)  # fade0=2

def Fuel_2():
    fade_off()
    color_all(127,127,127)  # all white low-brightness
    pattern_ctrl(3,5,5)  # pg_mode=3 (8 pattern slots), pg_time=5 (1s), fade1=5
    pattern_fade(0b00000111)
    pattern_rgbn(1,0b00000111)
    pattern_rgbn(2,0b00000111)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(1)  # run 1 time
    global_on(2)  # fade0=2

def Fuel_1():
    fade_off()
    color_rgbn(1,127,127,127)  # rgb1=white low-brightness
    pattern_ctrl(3,5,5)  # pg_mode=3 (8 pattern slots), pg_time=5 (1s), fade1=5
    pattern_fade(0b00000111)
    pattern_rgbn(1,0b00000111)
    pattern_rgbn(2,0b00000000)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(1)  # run 1 time
    global_on(2)  # fade0=2

def Fuel_Empty():
    fade_off()
    color_rgbn(1,127,0,0)  # rgb1=red low-brightness
    pattern_ctrl(3,0,0)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=0
    pattern_fade(0b01010101)
    pattern_rgbn(1,0b01010101)  # rgb1 flashing
    pattern_rgbn(2,0b00000000)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b00000000)
    pattern_watchdog(2)  # cycles=2 at 1.5s/cycle = 3s, then turn off
    global_on(0)  # fade0=0

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

def BT_Pair_Mode():
    fade_off()
    color_rgbn(1,0,127,0)  # rgb1=green low-brightness
    color_rgbn(4,0,0,255)  # rgb4=blue
    pattern_ctrl(3,4,1)  # pg_mode=3 (8 pattern slots), pg_time=4 (750ms), fade1=2
    pattern_fade(0b01010101)
    pattern_rgbn(1,0b11111111)  # rgb1 on continuous
    pattern_rgbn(2,0b00000000)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b01010101)  # rgb4 flashing 50% duty
    pattern_watchdog(20)  # turn off after 20cycles*8slots*750ms = 120sec or until interrupted
    global_on(1)  # fade0=1

def BT_Connecting():
    fade_off()
    color_rgbn(1,0,127,0)  # rgb1=green low-brightness
    color_rgbn(4,0,0,255)  # rgb4=blue
    pattern_ctrl(3,3,1)  # pg_mode=3 (8 pattern slots), pg_time=3 (500ms), fade1=2
    pattern_fade(0b11111111)
    pattern_rgbn(1,0b11111111)  # rgb1 on continuous
    pattern_rgbn(2,0b00000000)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b11111111)  # rgb4 on continuous
    pattern_watchdog(15)  # turn off after 15cycles*8slots*500ms = 60sec or until interrupted
    global_on(1)  # fade0=1

def BT_Connected():
    fade_off()
    color_rgbn(1,0,31,0)  # rgb1=green ultra-low-brightness
    color_rgbn(4,0,0,127)  # rgb4=blue low-brightness
    pattern_ctrl(3,3,3)  # pg_mode=3 (8 pattern slots), pg_time=3 (500ms), fade1=3
    pattern_fade(0b00010000)
    pattern_rgbn(1,0b11111111)  # rgb1 on continuous
    pattern_rgbn(2,0b00000000)
    pattern_rgbn(3,0b00000000)
    pattern_rgbn(4,0b00010000)  # rgb4 pulsing 1/8th duty
    pattern_watchdog(255)  # run forever until interrupted
    global_on(2)  # fade0=2

def Knight_Rider_2000(cycles):
    fade_off()
    color_all(255,0,0)  # all red
    pattern_ctrl(3,0,2)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=2
    pattern_fade(0b11111111)
    pattern_rgbn(1,0b10000001)
    pattern_rgbn(2,0b01000010)
    pattern_rgbn(3,0b00100100)
    pattern_rgbn(4,0b00011000)
    pattern_watchdog(cycles)  # turn off after n cycles at 1.5s/cycle or until interrupted
    global_on(2)  # fade0=2

def Audi_Turn_Signal(cycles):
    fade_off()
    color_all(255,191,0)  # all amber
    pattern_ctrl(3,0,6)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=6
    pattern_fade(0b00111111)
    pattern_rgbn(1,0b00111111)
    pattern_rgbn(2,0b00111110)
    pattern_rgbn(3,0b00111100)
    pattern_rgbn(4,0b00111000)
    pattern_watchdog(cycles)  # turn off after n cycles at 1.5s/cycle or until interrupted
    global_on(0)  # fade0=0

def Google_Wave(cycles):
    fade_off()
    Google_Colors()
    pattern_ctrl(3,1,5)  # pg_mode=3 (8 pattern slots), pg_time=1 (250ms), fade1=5
    pattern_fade(0b11111111)
    pattern_rgbn(1,0b00000011)
    pattern_rgbn(2,0b00000110)
    pattern_rgbn(3,0b00001100)
    pattern_rgbn(4,0b00011000)
    pattern_watchdog(cycles)  # turn off after n cycles at 2s/cycle or until interrupted
    global_on(4)  # fade0=4

def Police_Bar(cycles):
    fade_off()
    color_rgbn(1,255,0,0)  # rgb1=red
    color_rgbn(2,255,191,0)  # rgb2=amber
    color_rgbn(3,255,191,0)  # rgb3=amber
    color_rgbn(4,0,63,255)  # rgb4=blue-azure
    pattern_ctrl(3,0,0)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=0
    pattern_fade(0b11111111)
    pattern_rgbn(1,0b00000101)
    pattern_rgbn(2,0b01010000)
    pattern_rgbn(3,0b01010000)
    pattern_rgbn(4,0b00000101)
    pattern_watchdog(cycles)  # turn off after n cycles at 1.5s/cycle or until interrupted
    global_on(2)  # fade0=2

def Moving_Rainbow(cycles):    # example code that doesn't use pattern generator
    global_reset()
    global_on(4)    # fade=4
    for i in range(cycles):
        for j in range(4):  # flow dim blue across RGBs
            color_rgbn(j+1,0,31,127)
            time.sleep(0.3)
        for j in range(4):  # flow blue across RGBs
            color_rgbn(j+1,0,63,255)
            time.sleep(0.3)
        for j in range(4):  # flow dim red across RGBs
            color_rgbn(j+1,127,0,0)
            time.sleep(0.3)
        for j in range(4):  # flow red across RGBs
            color_rgbn(j+1,255,0,0)
            time.sleep(0.3)
        for j in range(4):  # flow dim green across RGBs
            color_rgbn(j+1,0,95,0)
            time.sleep(0.3)
        for j in range(4):  # flow green across RGBs
            color_rgbn(j+1,0,191,0)
            time.sleep(0.3)
    Power_Off(1)  # power off and wait 1s

def Indicators_Example():
    # Run pattern generator continuously,
    #   but dynamically change rgb colors and blink rates.
    global_reset()
    pattern_ctrl(3,0,0)  # pg_mode=3 (8 pattern slots), pg_time=0 (188ms), fade1=0 (but unused)
    pattern_watchdog(255)  # run forever until interrupted
    global_on(2)  # fade0=2
    color_all(0,63,0)  # all green ultra-low-brightness
    pattern_all(0b11111111)  # all on continuous
    time.sleep(3)
    color_rgbn(3,127,127,0)  # rgb3=yellow low-brightness
    pattern_rgbn(3,0b00001111)  # rgb3=blink slow
    time.sleep(6)
    color_rgbn(3,255,127,0)  # rgb3=orange
    pattern_rgbn(3,0b00110011)  # rgb3=blink medium
    time.sleep(6)
    color_rgbn(3,255,0,0)  # rgb3=red
    pattern_rgbn(3,0b10101010)  # rgb3=blink fast
    global_on(1)  # change to fade0=1
    time.sleep(6)
    global_on(2)  # change to fade0=2
    pattern_rgbn(3,0b00000000)  # rgb3=off
    time.sleep(2)
    color_rgbn(4,0,0,127)  # rgb4=blue low-brightness
    pattern_rgbn(4,0b00001111)  # rgb4=blink slow
    time.sleep(6)
    color_rgbn(2,127,127,0)  # rgb2=yellow low-brightness
    pattern_rgbn(2,0b11110000)  # rgb2=blink slow out of phase
    time.sleep(8)
    Power_Off(1)  # power off and wait 1s

# ---- large text character display ----
#import terminalio
#from adafruit_display_text import bitmap_label
#text_area = bitmap_label.Label(terminalio.FONT, text="Kinetic", scale=3)
#text_area.x = 10
#text_area.y = 10
#board.DISPLAY.show(text_area)
# --------------------------------------

# ----- Bitmap Display -----------------
from displayio import OnDiskBitmap, TileGrid, Group
main_group = Group()
blinka_img = OnDiskBitmap("images/penguin.bmp")
tile_grid = TileGrid(bitmap=blinka_img, pixel_shader=blinka_img.pixel_shader)
main_group.append(tile_grid)
board.DISPLAY.show(main_group)
tile_grid.x = board.DISPLAY.width // 2 - blinka_img.width // 2
# --------------------------------------

# -------Web server---------------------
import microcontroller
import socketpool
import wifi

from adafruit_httpserver import Server, Request, JSONResponse


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)

# (Optional) Allow cross-origin requests.
server.headers = {
    "Access-Control-Allow-Origin": "*",
}


@server.route("/cpu-information", append_slash=True)
def cpu_information_handler(request: Request):
    """
    Return the current CPU temperature, frequency, and voltage as JSON.
    """

    data = {
        "temperature": microcontroller.cpu.temperature,
        "frequency": microcontroller.cpu.frequency,
        "voltage": microcontroller.cpu.voltage,
    }

    return JSONResponse(request, data)


server.serve_forever(str(wifi.radio.ipv4_address))
# --------------------------------------




Chip_Status_Check()  # dim white, then read the ID and MONITOR registers for fault status
Google_Wave(6)          # show Google Wave lighting annimation for 6cycles at 2s/cycle
while True:
    #ed.value = True
    #time.sleep(2)
    #led.value = False
    #time.sleep(2)

    PatternCautionFlash(1)            #  13)  def PatternCautionFlash(cycles):
    PowerUp_Boot_Sequence() # show a PowerUp Boot Sequence lighting annimation
    Breathe_All_Blue(4)     # breathe blue for cycles=4 at 4s/cycle = 16s
