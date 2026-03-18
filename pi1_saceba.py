import pygame
import random
import time
import threading
import socket
import json
import numpy as np
import requests
import os

from google import genai

# ===========================================
# 1. INIZIALIZZAZIONE PYGAME E AUDIO
# ===========================================
os.environ['SDL_VIDEODRIVER'] = 'x11'
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'

pygame.init()
SAMPLE_RATE = 44100
pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=6, buffer=1024)

# ===========================================
# CONFIGURAZIONE RISOLUZIONI E RETE
# ===========================================
W1, H1 = 800, 600
W2, H2 = 800, 600
TOT_W = W1 + W2
MAX_H = max(H1, H2)

GEMINI_KEY = "AIzaSyDF58f-kwUCqJYbrG4stxLecmW-R5KXrBA"
MODELLO = "gemini-3-flash-preview"
N2YO_KEY = "E6GCA2-SE7T3P-9AY5UD-5OIK"

SAT_LAT = 45.85; SAT_LNG = 9.01; SAT_ALT = 300; SAT_RAGGIO = 70

PI2_IP = "192.168.1.105"
PI2_PORT = 6000
ARDUINO_PORT = 5000

client = genai.Client(api_key=GEMINI_KEY)

# ===========================================
# CONFIGURAZIONE ATTIVATORE (SILENZIO & DISTANZA)
# ===========================================
ACT_SOGLIA_DIST_WAKE = 100  
ACT_SOGLIA_DIST_SLEEP = 150 
ACT_SOGLIA_RUMORE = 1500    
ACT_TIMEOUT_SLEEP = 10.0    

act_dist = 999
act_noise = 0
ultimo_movimento = time.time()

# ===========================================
# PARAMETRI AUDIO LIVE (EDITOR AVANZATO)
# ===========================================
# Valori per il BEEP MORSE
beep_freq = 24.0
beep_amp = 24.19
beep_offset = 0.75
beep_bias = 0.50  # 0.5=Triangolo, 0.01=Sawtooth
beep_phase = 0.00

# Valori per l'INTERFERENZA (GLITCH)
int_freq = 23.0
int_amp = 1.90
int_offset = -0.10
int_bias = 0.96
int_phase = 0.00

editor_mode = False
editor_index = 0 # Da 0 a 9

# ===========================================
# DATI E VARIABILI GLOBALI
# ===========================================
stato_sistema = "STANDBY" 
inizio_boot = 0
DURATA_BOOT = 5.0

valori = {"P1": {"dist": 999, "vibr": 0.0}, "P2": {"dist": 999, "vibr": 0.0}, "P3": {"dist": 999, "vibr": 0.0}}
lock_valori = threading.Lock()

sat_count = 0; sat_nomi = []; sat_data_raw = []; iss_presente = False; sat_energia = 0.0
lock_sat = threading.Lock(); ultimo_sat_update = 0

energia_spirito = 0.0; agitazione = 0.0; presenza_rilevata = False; parabole_attive = 0
messaggio_spirito = ""; intensita_spirito = 0; spirito_attivo = False
ultimo_stato_gemini = "STANDBY"; ultimo_errore = ""

sequenza_lettere = []; lettera_index = 0; simbolo_index = 0
morse_timer = 0; morse_in_corso = False; fase_morse = "off"
schermo_morse_stato = {"P1": False, "P2": False, "P3": False}; suono_avviato = False
simbolo_p3_corrente = "punto"

prossima_sequenza = []
prossimo_messaggio = ""

glitch_attivo = {"P1": False, "P2": False, "P3": False}
ultimo_glitch = {"P1": 0, "P2": 0, "P3": 0}
memoria_spirito = []; MAX_MEMORIA = 15

sock_pi2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def invia_a_pi2():
    try:
        msg = json.dumps({
            "stato_sistema": stato_sistema,
            "vibr_p3": valori["P3"]["vibr"],
            "act_noise": act_noise, 
            "morse": schermo_morse_stato.get("P3", False), 
            "simbolo": simbolo_p3_corrente,
            "glitch": glitch_attivo.get("P3", False), 
            "energia": round(energia_spirito, 3), 
            "agitazione": round(agitazione, 3), 
            "messaggio": messaggio_spirito, 
            "spirito_attivo": spirito_attivo
        })
        sock_pi2.sendto(msg.encode(), (PI2_IP, PI2_PORT))
    except: pass

# ===========================================
# AUDIO - SINTESI CUSTOM VARIABLE-BIAS
# ===========================================
def genera_tono_custom(frequenza, durata, volume=0.5):
    n_samples = int(SAMPLE_RATE * durata)
    t = np.linspace(0, durata, n_samples, False)
    
    phase_array = (t * frequenza + beep_phase) % 1.0
    b = np.clip(beep_bias, 1e-5, 1 - 1e-5)
    
    onda = np.empty_like(phase_array)
    rising = phase_array < b
    falling = ~rising
    
    onda[rising] = -1.0 + (phase_array[rising] / b) * 2.0
    onda[falling] = 1.0 - ((phase_array[falling] - b) / (1.0 - b)) * 2.0
    
    onda = (onda * beep_amp) + beep_offset
    onda = np.clip(onda, -1.0, 1.0)
    
    fi = min(int(SAMPLE_RATE * 0.01), n_samples // 4)
    fo = min(int(SAMPLE_RATE * 0.02), n_samples // 4)
    if fi > 0: onda[:fi] *= np.linspace(0, 1, fi)
    if fo > 0: onda[-fo:] *= np.linspace(1, 0, fo)
    
    onda = onda * volume
    stereo = np.column_stack((onda, onda))
    return pygame.sndarray.make_sound((stereo * 32767).astype(np.int16))

def genera_interferenza_custom(durata, volume=0.3):
    n_samples = int(SAMPLE_RATE * durata)
    t = np.linspace(0, durata, n_samples, False)
    
    phase_array = (t * int_freq + int_phase) % 1.0
    b = np.clip(int_bias, 1e-5, 1 - 1e-5)
    
    onda = np.empty_like(phase_array)
    rising = phase_array < b
    falling = ~rising
    
    onda[rising] = -1.0 + (phase_array[rising] / b) * 2.0
    onda[falling] = 1.0 - ((phase_array[falling] - b) / (1.0 - b)) * 2.0
    
    rumore = np.random.uniform(-1, 1, n_samples)
    onda = onda + (rumore * 0.5) 
    
    onda = (onda * int_amp) + int_offset
    onda = np.clip(onda, -1.0, 1.0)
    
    f = min(int(SAMPLE_RATE * 0.002), n_samples // 4)
    if f > 0: onda[:f] *= np.linspace(0, 1, f); onda[-f:] *= np.linspace(1, 0, f)
    
    onda = onda * volume
    stereo = np.column_stack((onda, onda))
    return pygame.sndarray.make_sound((stereo * 32767).astype(np.int16))

# Variabili Suoni
snd_wakeup = None
snd_static = None
toni = {}
canali = {}
ch_noise = {}

def aggiorna_suoni_dinamici():
    global snd_wakeup, snd_static, toni
    snd_wakeup = genera_tono_custom(beep_freq, 0.6, 0.6) 
    snd_static = genera_interferenza_custom(0.08, 0.3)
    
    for i, ns in enumerate(["P1", "P2", "P3"]):
        f = beep_freq + (i * 2.0)
        toni[ns] = {
            "punto": genera_tono_custom(f, 0.18, 0.5), 
            "linea": genera_tono_custom(f, 0.45, 0.5)
        }

for i, ns in enumerate(["P1", "P2", "P3"]):
    canali[ns] = pygame.mixer.Channel(i)      
    ch_noise[ns] = pygame.mixer.Channel(i+3)

aggiorna_suoni_dinamici()

def play_test_audio(test_interferenza=False):
    if test_interferenza:
        if not ch_noise["P1"].get_busy(): ch_noise["P1"].play(snd_static)
    else:
        if not canali["P1"].get_busy(): canali["P1"].play(toni["P1"]["punto"])

# ===========================================
# SENSORI UDP E API
# ===========================================
def leggi_sensori_udp():
    global act_dist, act_noise
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', ARDUINO_PORT))
    sock.settimeout(0.1)
    while True:
        try:
            data, addr = sock.recvfrom(256)
            linea = data.decode().strip()
            
            if linea.startswith("ACT|"):
                parti = linea.split('|')
                if len(parti) >= 3:
                    try:
                        act_dist = int(parti[1].split(':')[1])
                        act_noise = int(parti[2].split(':')[1])
                    except: pass
                    
            elif '|' in linea:
                parti = linea.split('|'); nome = parti[0].strip()
                if nome in valori:
                    try:
                        dist = max(0, min(int(parti[1].split(':')[1].replace('cm','').strip()), 999))
                        vibr = max(0.0, min(float(parti[2].split(':')[1].strip()), 10.0))
                        with lock_valori: valori[nome] = {"dist": dist, "vibr": vibr}
                    except: pass
        except socket.timeout: pass
        except: pass

def aggiorna_satelliti():
    global sat_count, sat_nomi, sat_data_raw, iss_presente, ultimo_sat_update, sat_energia
    while True:
        if stato_sistema == "STANDBY": 
            time.sleep(2)
            continue
        try:
            url = f"https://api.n2yo.com/rest/v1/satellite/above/{SAT_LAT}/{SAT_LNG}/{SAT_ALT}/{SAT_RAGGIO}/0/&apiKey={N2YO_KEY}"
            r = requests.get(url, timeout=10); data = r.json()
            with lock_sat:
                sat_count = data.get("info", {}).get("satcount", 0)
                sat_data_raw = data.get("above", [])[:20]
                sat_nomi = [s.get("satname", "?") for s in sat_data_raw]
                iss_presente = any("ISS" in n.upper() for n in sat_nomi)
                if sat_count <= 0: sat_energia = 0.0
                elif sat_count < 10: sat_energia = sat_count / 30.0
                elif sat_count < 30: sat_energia = 0.3 + (sat_count - 10) / 40.0
                else: sat_energia = min(1.0, 0.5 + sat_count / 100.0)
                if iss_presente: sat_energia = min(1.0, sat_energia + 0.3)
                ultimo_sat_update = time.time()
        except Exception as e: pass
        time.sleep(4)

def calcola_disturbo(nome):
    with lock_valori: dist = valori[nome]["dist"]
    if dist >= 200: return 0.0
    elif dist <= 20: return 1.0
    else: return 1.0 - (dist / 200.0)

def calcola_disturbo_medio():
    with lock_valori: dists = [valori[p]["dist"] for p in ["P1","P2","P3"]]
    m = min(dists)
    if m >= 200: return 0.0
    elif m <= 20: return 1.0
    else: return 1.0 - (m / 200.0)

def aggiorna_stato_locale():
    global energia_spirito, agitazione, presenza_rilevata, parabole_attive
    with lock_valori: v = {k: dict(val) for k, val in valori.items()}
    attive = 0; min_dist = 999; max_vibr = 0
    for nome in ["P1","P2","P3"]:
        d = v[nome]["dist"]; vb = v[nome]["vibr"]
        if d < min_dist: min_dist = d
        if vb > max_vibr: max_vibr = vb
        if d < 150 or vb > 0.15: attive += 1
        disturbo = calcola_disturbo(nome)
        if disturbo > 0.1:
            if random.random() < disturbo*0.08 and time.time()-ultimo_glitch[nome]>0.3:
                glitch_attivo[nome] = True; ultimo_glitch[nome] = time.time()
            elif time.time()-ultimo_glitch[nome]>0.1: glitch_attivo[nome] = False
        else: glitch_attivo[nome] = False
    parabole_attive = attive; presenza_rilevata = min_dist < 200
    ts = 0.0
    if attive==1: ts=0.3
    elif attive==2: ts=0.5
    elif attive>=3: ts=0.7
    if min_dist<50: ts=min(1.0,ts+0.3)
    elif min_dist<100: ts=min(1.0,ts+0.15)
    with lock_sat: se=sat_energia
    tgt = ts*0.6 + se*0.4
    energia_spirito += (tgt-energia_spirito)*0.05
    energia_spirito = max(0.0,min(1.0,energia_spirito))
    ta = min(1.0, max_vibr*2.0)
    if ta>agitazione: agitazione+=(ta-agitazione)*0.3
    else: agitazione+=(ta-agitazione)*0.05
    agitazione = max(0.0,min(1.0,agitazione))

CODICE_MORSE = {'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..','J':'.---','K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...','T':'-','U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..', ' ':'/'}

def genera_sequenza_spalmata(msg):
    schermi=["P1","P2","P3"]; seq=[]
    testo="".join(c for c in msg.upper().strip() if c in CODICE_MORSE or c==' ')
    for i,ch in enumerate(testo):
        if ch==' ': seq.append({"schermo":None,"simboli":[],"lettera":" ","tipo":"spazio"})
        elif ch in CODICE_MORSE and CODICE_MORSE[ch]: seq.append({"schermo":schermi[i%3],"simboli":list(CODICE_MORSE[ch]),"lettera":ch,"tipo":"lettera"})
    return seq

def costruisci_prompt():
    with lock_valori: v={k:dict(val) for k,val in valori.items()}
    with lock_sat: sc=sat_count; iss=iss_presente; se=sat_energia
    mem=", ".join(memoria_spirito[-10:]) if memoria_spirito else "none"
    return f"""You are a ghost. You worked in a cement factory. You are confused, tired. You speak only in fragments.
RULES: ONE word only. Maximum two words. NEVER three or more.
SENSORS: energy={energia_spirito:.1f} agitation={agitazione:.1f} parabolas={parabole_attive}/3
SATELLITES: {sc} overhead {"ISS PASSING" if iss else ""} sat_energy={se:.1f}
ALREADY SAID: {mem}
If energy < 0.15: {{"comunicare": false}}
Otherwise: {{"comunicare": true, "messaggio": "WORD", "intensita": 1-10}}
JSON only."""

def chiedi_spirito():
    global spirito_attivo, messaggio_spirito, intensita_spirito
    global sequenza_lettere, lettera_index, simbolo_index, morse_in_corso, morse_timer
    global fase_morse, ultimo_stato_gemini, ultimo_errore
    global prossima_sequenza, prossimo_messaggio 
    
    while True:
        if stato_sistema != "ACTIVE": 
            ultimo_stato_gemini = "STANDBY / BOOTING"
            spirito_attivo = False
            morse_in_corso = False
            sequenza_lettere = []
            prossima_sequenza = [] 
            schermo_morse_stato["P1"]=schermo_morse_stato["P2"]=schermo_morse_stato["P3"]=False
            time.sleep(2)
            continue
            
        if energia_spirito<0.1:
            spirito_attivo=False; messaggio_spirito=""; morse_in_corso=False; sequenza_lettere=[]
            prossima_sequenza = []
            schermo_morse_stato["P1"]=schermo_morse_stato["P2"]=schermo_morse_stato["P3"]=False
            ultimo_stato_gemini="DORMANT"; time.sleep(3); continue
            
        try:
            ultimo_stato_gemini="API..."
            response=client.models.generate_content(model=MODELLO,contents=costruisci_prompt())
            testo=response.text.strip().replace("```json","").replace("```","").strip()
            risposta=json.loads(testo); ultimo_errore=""
            if risposta.get("comunicare"):
                spirito_attivo=True
                nuovo_messaggio = risposta.get("messaggio","")
                intensita_spirito=min(10,max(1,risposta.get("intensita",5)))
                memoria_spirito.append(nuovo_messaggio)
                if len(memoria_spirito)>MAX_MEMORIA: memoria_spirito.pop(0)
                
                prossima_sequenza = genera_sequenza_spalmata(nuovo_messaggio)
                prossimo_messaggio = nuovo_messaggio
                ultimo_stato_gemini=f"READY:{nuovo_messaggio}[{intensita_spirito}]"
            else:
                spirito_attivo=False
                ultimo_stato_gemini="SILENT"
        except Exception as e:
            ultimo_errore=str(e)[:60]; ultimo_stato_gemini="ERROR"
            
        if energia_spirito>0.7: time.sleep(4)
        elif energia_spirito>0.3: time.sleep(6)
        else: time.sleep(8)

# ===========================================
# PYGAME - GESTIONE GRAFICA E MAIN LOOP
# ===========================================
win_main = pygame.display.set_mode((TOT_W, MAX_H), pygame.NOFRAME)
pygame.mouse.set_visible(False)

font_overlay = pygame.font.Font(None, 28)
font_nasa = pygame.font.SysFont('monospace', 28, bold=True)
mostra_debug = True 
clock = pygame.time.Clock()

def scanlines(s, x, y, w, h):——
    for sy in range(y, y+h, 2): pygame.draw.line(s, (0,0,0), (x,sy), (x+w,sy))

def draw_crt(s, x, y, w, h, nome, morse_on):
    dist = calcola_disturbo(nome); gl = glitch_attivo.get(nome, False)
    if morse_on:
        if dist>0.3 and random.random()<dist*0.6:
            if random.random()<dist*0.4: pygame.draw.rect(s,(0,0,0),(x,y,w,h))
            else:
                lm=max(60,int(230-dist*random.randint(80,200)))
                pygame.draw.rect(s,(lm,lm,lm),(x,y,w,h))
                for _ in range(int(dist*8)):
                    iy=random.randint(y,y+h-3)
                    pygame.draw.rect(s,(random.randint(0,40),)*3,(x,iy,w,random.randint(1,5)))
        else: pygame.draw.rect(s,(230,230,230),(x,y,w,h))
        scanlines(s,x,y,w,h)
    elif gl:
        lm=random.randint(20,int(60+agitazione*120))
        pygame.draw.rect(s,(lm,lm,lm),(x,y,w,h))
        for _ in range(int(2+agitazione*6)):
            iy=random.randint(y,y+h-3)
            pygame.draw.rect(s,(random.randint(lm//2,lm),)*3,(x,iy,w,random.randint(1,int(2+agitazione*5))))
        scanlines(s,x,y,w,h)
        if not ch_noise[nome].get_busy(): ch_noise[nome].play(snd_static)
    else:
        bl=int(energia_spirito*8)
        pygame.draw.rect(s,(bl,bl,bl),(x,y,w,h))
        if energia_spirito>0.2 and random.random()<energia_spirito*0.03:
            fy=random.randint(y,y+h-2); fl=random.randint(0,int(energia_spirito*15))
            pygame.draw.line(s,(fl,fl,fl),(x,fy),(x+w,fy))
        scanlines(s,x,y,w,h)

def draw_boot_sonar(s, x, y, w, h, dist):
    col_ambra = (255, 170, 0)
    pygame.draw.rect(s, (0, 0, 0), (x, y, w, h))
    for i in range(0, w, 50): pygame.draw.line(s, (50, 30, 0), (x+i, y), (x+i, y+h))
    for i in range(0, h, 50): pygame.draw.line(s, (50, 30, 0), (x, y+i), (x+w, y+i))
    s.blit(font_nasa.render(">>> SYS INIT: SONAR MODULE", True, col_ambra), (x + 30, y + 50))
    s.blit(font_nasa.render(f"TARGET DISTANCE: {dist} cm", True, col_ambra), (x + 30, y + 100))
    prog = int((time.time() * 5) % 15)
    s.blit(font_nasa.render("CALIBRATING" + "." * prog, True, col_ambra), (x + 30, y + 150))
    scan_y = y + int((time.time() * 200) % h)
    pygame.draw.line(s, col_ambra, (x, scan_y), (x+w, scan_y), 3)
    scanlines(s, x, y, w, h)

def draw_boot_sat(s, x, y, w, h, sats, energia):
    col_ciano = (0, 255, 255)
    pygame.draw.rect(s, (0, 0, 0), (x, y, w, h))
    for i in range(0, w, 50): pygame.draw.line(s, (0, 30, 50), (x+i, y), (x+i, y+h))
    for i in range(0, h, 50): pygame.draw.line(s, (0, 30, 50), (x, y+i), (x+w, y+i))
    s.blit(font_nasa.render(">>> SYS INIT: ORBITAL TELEMETRY", True, col_ciano), (x + 30, y + 50))
    s.blit(font_nasa.render(f"SATELLITES DETECTED: {sats}", True, col_ciano), (x + 30, y + 100))
    s.blit(font_nasa.render(f"SIGNAL LOCK: {energia*100:.1f} %", True, col_ciano), (x + 30, y + 150))
    for i in range(8):
        hex_str = "".join([random.choice("0123456789ABCDEF") for _ in range(16)])
        s.blit(font_nasa.render(f"0x{hex_str}", True, (0, 150, 150)), (x + 30, y + 250 + i*30))
    scanlines(s, x, y, w, h)

threading.Thread(target=leggi_sensori_udp, daemon=True).start()
threading.Thread(target=aggiorna_satelliti, daemon=True).start()
threading.Thread(target=chiedi_spirito, daemon=True).start()

running = True
mt = time.time()

while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT: running = False
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_q): running = False
            if ev.key == pygame.K_d: mostra_debug = not mostra_debug
            if ev.key == pygame.K_m:
                messaggio_spirito = "SOS NASA"
                sequenza_lettere = genera_sequenza_spalmata(messaggio_spirito)
                lettera_index = 0
                simbolo_index = 0
                morse_in_corso = True
                fase_morse = "off"
                mt = time.time()
                ultimo_stato_gemini = "TEST MANUALE"
                
            # ================= EDITOR AUDIO COMANDI =================
            if ev.key == pygame.K_e and mostra_debug:
                editor_mode = not editor_mode
                
            if editor_mode and mostra_debug:
                if ev.key == pygame.K_UP:
                    editor_index = (editor_index - 1) % 10
                elif ev.key == pygame.K_DOWN:
                    editor_index = (editor_index + 1) % 10
                elif ev.key == pygame.K_LEFT:
                    if editor_index == 0: beep_freq = max(5.0, beep_freq - 1.0)
                    elif editor_index == 1: beep_amp -= 0.2
                    elif editor_index == 2: beep_offset -= 0.05
                    elif editor_index == 3: beep_bias = max(0.01, beep_bias - 0.05)
                    elif editor_index == 4: beep_phase = (beep_phase - 0.05) % 1.0
                    
                    elif editor_index == 5: int_freq = max(5.0, int_freq - 1.0)
                    elif editor_index == 6: int_amp -= 0.2
                    elif editor_index == 7: int_offset -= 0.05
                    elif editor_index == 8: int_bias = max(0.01, int_bias - 0.05)
                    elif editor_index == 9: int_phase = (int_phase - 0.05) % 1.0
                    
                    aggiorna_suoni_dinamici()
                    play_test_audio(test_interferenza=(editor_index >= 5))
                    
                elif ev.key == pygame.K_RIGHT:
                    if editor_index == 0: beep_freq += 1.0
                    elif editor_index == 1: beep_amp += 0.2
                    elif editor_index == 2: beep_offset += 0.05
                    elif editor_index == 3: beep_bias = min(0.99, beep_bias + 0.05)
                    elif editor_index == 4: beep_phase = (beep_phase + 0.05) % 1.0
                    
                    elif editor_index == 5: int_freq += 1.0
                    elif editor_index == 6: int_amp += 0.2
                    elif editor_index == 7: int_offset += 0.05
                    elif editor_index == 8: int_bias = min(0.99, int_bias + 0.05)
                    elif editor_index == 9: int_phase = (int_phase + 0.05) % 1.0
                    
                    aggiorna_suoni_dinamici()
                    play_test_audio(test_interferenza=(editor_index >= 5))

    win_main.fill((0, 0, 0))

    if stato_sistema == "STANDBY":
        if act_dist < ACT_SOGLIA_DIST_WAKE and act_noise < ACT_SOGLIA_RUMORE:
            stato_sistema = "BOOTING"
            inizio_boot = time.time()
            ultimo_movimento = time.time()
            ch_noise["P1"].play(snd_wakeup)
    else:
        if act_dist < ACT_SOGLIA_DIST_SLEEP:
            ultimo_movimento = time.time()
        elif time.time() - ultimo_movimento > ACT_TIMEOUT_SLEEP:
            stato_sistema = "STANDBY"

    if stato_sistema == "BOOTING":
        if time.time() - inizio_boot > DURATA_BOOT:
            stato_sistema = "ACTIVE"
        else:
            with lock_valori: v = {k: dict(val) for k, val in valori.items()}
            draw_boot_sonar(win_main, 0, 0, W1, H1, v["P1"]["dist"])
            draw_boot_sat(win_main, W1, 0, W2, H2, sat_count, sat_energia)
            invia_a_pi2()

    elif stato_sistema == "ACTIVE":
        aggiorna_stato_locale()
        schermo_morse_stato["P1"] = schermo_morse_stato["P2"] = schermo_morse_stato["P3"] = False

        if morse_in_corso and sequenza_lettere and lettera_index < len(sequenza_lettere):
            step = sequenza_lettere[lettera_index]; now = time.time(); dt = now - mt
            if step["tipo"] == "spazio":
                suono_avviato = False
                if dt > 0.6: mt = now; lettera_index += 1; simbolo_index = 0
            elif step["tipo"] == "lettera":
                if simbolo_index < len(step["simboli"]):
                    sim = step["simboli"][simbolo_index]
                    if fase_morse == "off":
                        fase_morse = "on"; mt = now
                        schermo_morse_stato[step["schermo"]] = True; suono_avviato = False
                    elif fase_morse == "on":
                        dur = 0.18 if sim == '.' else 0.45
                        d = calcola_disturbo_medio()
                        with lock_sat: se = sat_energia
                        dur *= (1.0 - se * 0.2)
                        if d > 0.2: dur += random.uniform(-0.04, 0.04) * d
                        if not suono_avviato:
                            ts = "punto" if sim == '.' else "linea"
                            sch = step["schermo"]
                            if sch == "P3": simbolo_p3_corrente = ts
                                
                            if sch in canali: 
                                if d < 0.3 or random.random() > d * 0.4:
                                    canali[sch].play(toni[sch][ts])
                            suono_avviato = True
                        if dt > dur:
                            fase_morse = "pausa_simbolo"; mt = now; suono_avviato = False
                        else:
                            schermo_morse_stato[step["schermo"]] = True
                    elif fase_morse == "pausa_simbolo":
                        suono_avviato = False
                        if dt > 0.1: simbolo_index += 1; fase_morse = "off"; mt = now
                else:
                    suono_avviato = False
                    if fase_morse != "pausa_lettera": fase_morse = "pausa_lettera"; mt = now
                    elif dt > 0.3: lettera_index += 1; simbolo_index = 0; fase_morse = "off"; mt = now
                    
        elif morse_in_corso and lettera_index >= len(sequenza_lettere):
            suono_avviato = False
            if time.time() - mt > 2.0: 
                if prossima_sequenza:
                    sequenza_lettere = prossima_sequenza
                    messaggio_spirito = prossimo_messaggio
                    prossima_sequenza = []
                    prossimo_messaggio = ""
                lettera_index = 0
                simbolo_index = 0
                fase_morse = "off"
                mt = time.time()
                
        elif not morse_in_corso and prossima_sequenza:
            sequenza_lettere = prossima_sequenza
            messaggio_spirito = prossimo_messaggio
            prossima_sequenza = []
            prossimo_messaggio = ""
            lettera_index = 0
            simbolo_index = 0
            morse_in_corso = True
            fase_morse = "off"
            mt = time.time()

        invia_a_pi2()
        draw_crt(win_main, 0, 0, W1, H1, "P1", schermo_morse_stato["P1"])
        draw_crt(win_main, W1, 0, W2, H2, "P2", schermo_morse_stato["P2"])

        if glitch_attivo.get("P3", False):
            if not ch_noise["P3"].get_busy(): ch_noise["P3"].play(snd_static)
            
    else:
        invia_a_pi2()

    # ================== PANNELLO DI DEBUG ==================
    if mostra_debug:
        with lock_valori: v = {k: dict(val) for k, val in valori.items()}
        with lock_sat: sc = sat_count; se = sat_energia; iss = iss_presente
            
        tracker_morse = "[ NESSUNA TRASMISSIONE ]"
        if morse_in_corso and sequenza_lettere:
            if lettera_index < len(sequenza_lettere):
                step = sequenza_lettere[lettera_index]
                if step["tipo"] == "lettera":
                    simboli_tot = "".join(step["simboli"])
                    simbolo_att = step["simboli"][simbolo_index] if simbolo_index < len(step["simboli"]) else " "
                    tracker_morse = f"{step['schermo']} | Lettera: {step['lettera']} [{simboli_tot}] -> Esegue: {simbolo_att}"
                else:
                    tracker_morse = "[ SPAZIO TRA LETTERE ]"
            else:
                tracker_morse = "[ PAUSA TRA LE PAROLE (2 Sec) ]"

        debug_lines = [
            "=== SACEBA SYSTEM DEBUG ===",
            f"STATO MAIN    : {stato_sistema}",
            f"ACTIVATOR     : Dist = {act_dist} cm | Noise = {act_noise} / {ACT_SOGLIA_RUMORE}",
            f"SATELLITI API : Num = {sc} | Energia = {se:.2f} | ISS = {'SI' if iss else 'NO'}",
            f"STATO SISTEMA : Energia Tot = {energia_spirito:.2f} | Agitazione = {agitazione:.2f}",
            f"INTELLIGENZA  : {ultimo_stato_gemini}",
            f"MORSE TRACKER : {tracker_morse}",
            ""
        ]
        
        # --- UI DELL'EDITOR AUDIO ESTESO ---
        if editor_mode:
            sel = ["  "] * 10
            sel[editor_index] = ">>"
            debug_lines.extend([
                "--- EDITOR AUDIO (FRECCE PER MODIFICARE) ---",
                f" [ MORSE BEEP ]",
                f"{sel[0]} Freq   : {beep_freq:.1f} Hz",
                f"{sel[1]} Amp.   : {beep_amp:.2f}",
                f"{sel[2]} Offset : {beep_offset:.2f}",
                f"{sel[3]} Bias   : {beep_bias:.2f}",
                f"{sel[4]} Phase  : {beep_phase:.2f}",
                f" [ INTERFERENZA (GLITCH) ]",
                f"{sel[5]} Freq   : {int_freq:.1f} Hz",
                f"{sel[6]} Amp.   : {int_amp:.2f}",
                f"{sel[7]} Offset : {int_offset:.2f}",
                f"{sel[8]} Bias   : {int_bias:.2f}",
                f"{sel[9]} Phase  : {int_phase:.2f}"
            ])
        else:
            debug_lines.append("[ Premi 'E' per Editor Audio | 'M' Test Morse | 'D' Nascondi ]")
        
        y_offset = 20
        for riga in debug_lines:
            testo_surf = font_overlay.render(riga, True, (50, 255, 50))
            sfondo_surf = pygame.Surface(testo_surf.get_size())
            sfondo_surf.set_alpha(200)
            sfondo_surf.fill((0, 0, 0))
            win_main.blit(sfondo_surf, (20, y_offset))
            win_main.blit(testo_surf, (20, y_offset))
            y_offset += 30

    pygame.display.flip()
    clock.tick(30)

pygame.mixer.quit()
pygame.quit()