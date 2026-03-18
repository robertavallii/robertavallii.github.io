import pygame
import socket
import json
import threading
import time
import random
import os

# ===========================================
# 1. INIZIALIZZAZIONE PYGAME (X11 & NOFRAME)
# ===========================================
# Questi due comandi forzano il Raspberry a nascondere la barra superiore
os.environ['SDL_VIDEODRIVER'] = 'x11'
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'

pygame.init()

# Il Raspberry 2 è muto, fa solo da terminale video P3
pygame.mixer.quit() 

# Usa la risoluzione massima del monitor collegato, nascondendo le cornici
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.NOFRAME)
W, H = screen.get_size()
pygame.display.set_caption("SACEBA - Terminale P3 (Satellite)")
pygame.mouse.set_visible(False)

font_nasa = pygame.font.SysFont('monospace', 28, bold=True)
clock = pygame.time.Clock()

# ===========================================
# 2. VARIABILI DI STATO (Ricevute dal PI 1)
# ===========================================
PORTA_UDP = 6000

dati_correnti = {
    "stato_sistema": "STANDBY",
    "morse": False,
    "glitch": False,
    "energia": 0.0,
    "agitazione": 0.0
}
lock_dati = threading.Lock()

# ===========================================
# 3. MOTORE DI RICEZIONE UDP (In background)
# ===========================================
def ricevi_comandi():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', PORTA_UDP))
    print(f"[*] Terminale P3 in ascolto sulla porta {PORTA_UDP}...")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            cmd = json.loads(data.decode())
            
            # Se vuoi fare debug di rete, togli il cancelletto alla riga sotto:
            # print("RICEVUTO:", cmd) 
            
            with lock_dati:
                dati_correnti["stato_sistema"] = cmd.get("stato_sistema", "STANDBY")
                dati_correnti["morse"] = cmd.get("morse", False)
                dati_correnti["glitch"] = cmd.get("glitch", False)
                dati_correnti["energia"] = cmd.get("energia", 0.0)
                dati_correnti["agitazione"] = cmd.get("agitazione", 0.0)
        except Exception as e:
            pass

threading.Thread(target=ricevi_comandi, daemon=True).start()

# ===========================================
# 4. FUNZIONI DI DISEGNO (EFFETTI CRT & BOOT)
# ===========================================
def scanlines(s, x, y, w, h):
    # Genera le righe nere orizzontali del vecchio tubo catodico
    for sy in range(y, y+h, 2): 
        pygame.draw.line(s, (0,0,0), (x,sy), (x+w,sy))

def draw_crt_p3(s, w, h, morse_on, glitch_on, energia, agitazione):
    # La logica visiva è identica al Pi 1, ma reagisce solo ai dati di P3
    disturbo = 0.0
    if energia < 0.3: disturbo = 1.0 - (energia / 0.3)
    
    if morse_on:
        if disturbo > 0.3 and random.random() < disturbo * 0.6:
            if random.random() < disturbo * 0.4: 
                pygame.draw.rect(s, (0,0,0), (0,0,w,h))
            else:
                lm = max(60, int(230 - disturbo * random.randint(80, 200)))
                pygame.draw.rect(s, (lm,lm,lm), (0,0,w,h))
                for _ in range(int(disturbo * 8)):
                    iy = random.randint(0, h-3)
                    pygame.draw.rect(s, (random.randint(0,40),)*3, (0, iy, w, random.randint(1,5)))
        else: 
            pygame.draw.rect(s, (230,230,230), (0,0,w,h))
        scanlines(s, 0, 0, w, h)
        
    elif glitch_on:
        lm = random.randint(20, int(60 + agitazione * 120))
        pygame.draw.rect(s, (lm,lm,lm), (0,0,w,h))
        for _ in range(int(2 + agitazione * 6)):
            iy = random.randint(0, h-3)
            pygame.draw.rect(s, (random.randint(lm//2,lm),)*3, (0, iy, w, random.randint(1, int(2 + agitazione * 5))))
        scanlines(s, 0, 0, w, h)
        
    else:
        bl = int(energia * 8)
        pygame.draw.rect(s, (bl,bl,bl), (0,0,w,h))
        if energia > 0.2 and random.random() < energia * 0.03:
            fy = random.randint(0, h-2)
            fl = random.randint(0, int(energia * 15))
            pygame.draw.line(s, (fl,fl,fl), (0, fy), (w, fy))
        scanlines(s, 0, 0, w, h)

def draw_boot_acoustic(s, w, h):
    # Schermata blu stile terminale NASA durante l'accensione
    col_blu = (50, 150, 255)
    s.fill((0, 0, 0))
    for i in range(0, w, 50): pygame.draw.line(s, (0, 30, 80), (i, 0), (i, h))
    for i in range(0, h, 50): pygame.draw.line(s, (0, 30, 80), (0, i), (w, i))
    
    s.blit(font_nasa.render(">>> SYS INIT: ACOUSTIC ARRAY P3", True, col_blu), (30, 50))
    s.blit(font_nasa.render("AWAITING SYNC...", True, col_blu), (30, 100))
    
    prog = int((time.time() * 5) % 15)
    s.blit(font_nasa.render("LINKING" + "." * prog, True, col_blu), (30, 150))
    
    scan_y = int((time.time() * 200) % h)
    pygame.draw.line(s, col_blu, (0, scan_y), (w, scan_y), 3)
    scanlines(s, 0, 0, w, h)

# ===========================================
# 5. MAIN LOOP
# ===========================================
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT: 
            running = False
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_q): 
                running = False

    # Legge i dati ricevuti dal Pi 1 in totale sicurezza
    with lock_dati:
        stato = dati_correnti["stato_sistema"]
        morse = dati_correnti["morse"]
        glitch = dati_correnti["glitch"]
        en = dati_correnti["energia"]
        ag = dati_correnti["agitazione"]

    # Motore Grafico a Stati
    if stato == "STANDBY":
        # Silenzio e Buio assoluto
        screen.fill((0, 0, 0))
        
    elif stato == "BOOTING":
        # La schermata di avvio del terzo terminale
        draw_boot_acoustic(screen, W, H)
        
    elif stato == "ACTIVE":
        # Renderizza il Morse o i Glitch
        draw_crt_p3(screen, W, H, morse, glitch, en, ag)

    pygame.display.flip()
    clock.tick(30)

pygame.quit()