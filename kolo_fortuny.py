"""
KOŁO FORTUNY
============
Uruchomienie:
    pip install pygame-ce      (działa też na najnowszym Pythonie; zwykły "pygame" też OK)
    python kolo_fortuny.py

Sterowanie:
    SPACJA / klik w koło / przycisk "KRĘĆ!"  -> zakręć kołem
    SPACJA / klik (gdy widać wynik)          -> usuń wylosowane pole i graj dalej
    R                                        -> reset (przywraca wszystkie pola)
    ESC                                      -> wyjście
"""

# =====================================================================
#  TUTAJ WPISZ SWOJE POLA NA KOLE  (jedno pole = jeden napis w cudzysłowie)
#  Możesz dać ich ile chcesz, ale ~20 wygląda najlepiej.
# =====================================================================
POLA = [
    "Pole 1",
    "Pole 2",
    "Pole 3",
    "Pole 4",
    "Pole 5",
    "Pole 6",
    "Pole 7",
    "Pole 8",
    "Pole 9",
    "Pole 10",
    "Pole 11",
    "Pole 12",
    "Pole 13",
    "Pole 14",
    "Pole 15",
    "Pole 16",
    "Pole 17",
    "Pole 18",
    "Pole 19",
    "Pole 20",
]
# =====================================================================

import array
import colorsys
import math
import random
import sys

import pygame

# --- Ustawienia ---
SZEROKOSC, WYSOKOSC = 1200, 800
PROMIEN = 330
SRODEK = (50 + PROMIEN, WYSOKOSC // 2 + 25)
PANEL_X = SRODEK[0] + PROMIEN + 70
FPS = 60

PREDKOSC_MIN, PREDKOSC_MAX = 720.0, 1260.0  # stopnie / sekundę na starcie
TARCIE = 0.55          # wykładnicze hamowanie (im więcej, tym krócej się kręci)
HAMOWANIE_STALE = 22.0  # stałe hamowanie (st/s^2), żeby ładnie dojechało do zera

TLO = (18, 20, 34)
BIALY = (255, 255, 255)
ZLOTY = (255, 200, 40)
SZARY = (150, 155, 175)

SAMPLE_RATE = 44100


# ---------------------------------------------------------------------
#  Dźwięki generowane w kodzie (nie trzeba żadnych plików .wav)
# ---------------------------------------------------------------------
def _zrob_dzwiek(probki, kanaly):
    """Zamienia listę próbek float (-1..1) na pygame.mixer.Sound."""
    dane = array.array("h")
    for p in probki:
        v = int(max(-1.0, min(1.0, p)) * 32000)
        for _ in range(kanaly):
            dane.append(v)
    return pygame.mixer.Sound(buffer=dane.tobytes())


def dzwiek_tyk(kanaly):
    """Krótkie, suche 'tyk' – jak plastikowy języczek uderzający w kołek."""
    dl = int(SAMPLE_RATE * 0.035)
    rnd = random.Random(7)
    probki = []
    for i in range(dl):
        t = i / SAMPLE_RATE
        obw_szybka = math.exp(-t / 0.0025)
        obw_wolna = math.exp(-t / 0.012)
        szum = (rnd.random() * 2 - 1) * obw_szybka * 0.7
        ton = (math.sin(2 * math.pi * 2400 * t) * 0.45
               + math.sin(2 * math.pi * 1150 * t) * 0.35) * obw_wolna
        probki.append((szum + ton) * 0.8)
    return _zrob_dzwiek(probki, kanaly)


def dzwiek_wygrana(kanaly):
    """Krótka fanfara po wylosowaniu."""
    nuty = [(523.25, 0.0), (659.25, 0.11), (783.99, 0.22), (1046.5, 0.33)]
    dl_calk = 1.3
    n = int(SAMPLE_RATE * dl_calk)
    probki = [0.0] * n
    for freq, start in nuty:
        s0 = int(start * SAMPLE_RATE)
        dl = 0.9 if freq > 1000 else 0.45
        for i in range(int(dl * SAMPLE_RATE)):
            j = s0 + i
            if j >= n:
                break
            t = i / SAMPLE_RATE
            obw = min(1.0, t / 0.01) * math.exp(-t / (dl / 3))
            probki[j] += (math.sin(2 * math.pi * freq * t)
                          + 0.35 * math.sin(2 * math.pi * freq * 2 * t)
                          + 0.15 * math.sin(2 * math.pi * freq * 3 * t)) * obw * 0.28
    return _zrob_dzwiek(probki, kanaly)


class Dzwieki:
    def __init__(self):
        self.ok = False
        try:
            pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 256)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(24)
            _, _, kanaly = pygame.mixer.get_init()
            self.tyk = dzwiek_tyk(kanaly)
            self.tyk.set_volume(0.6)
            self.wygrana = dzwiek_wygrana(kanaly)
            self.wygrana.set_volume(0.8)
            self.ok = True
        except Exception as e:  # brak karty dźwiękowej itp. – gramy bez dźwięku
            print("Dźwięk niedostępny:", e)

    def zagraj_tyk(self):
        if self.ok:
            self.tyk.play()

    def zagraj_wygrana(self):
        if self.ok:
            self.wygrana.play()


# ---------------------------------------------------------------------
#  Rysowanie koła
# ---------------------------------------------------------------------
def kolory_pol(n):
    kol = []
    for i in range(n):
        h = i / max(n, 1)
        s = 0.75 if i % 2 == 0 else 0.6
        v = 0.95 if i % 2 == 0 else 0.82
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        kol.append((int(r * 255), int(g * 255), int(b * 255)))
    return kol


def czcionka(rozmiar, pogrubiona=True):
    return pygame.font.Font(None, rozmiar) if not pogrubiona else pygame.font.SysFont(
        "dejavusans,arial,freesans", rozmiar, bold=True)


def dopasuj_tekst(tekst, max_szer, max_wys, start=34):
    """Zwraca wyrenderowany tekst zmniejszając czcionkę, a w ostateczności ucinając."""
    rozmiar = start
    while rozmiar >= 14:
        f = czcionka(rozmiar)
        w, h = f.size(tekst)
        if w <= max_szer and h <= max_wys:
            return f, tekst
        rozmiar -= 2
    f = czcionka(14)
    t = tekst
    while t and f.size(t + "…")[0] > max_szer:
        t = t[:-1]
    return f, t + "…"


def narysuj_kolo(pola):
    """Rysuje koło (w 2x rozdzielczości dla gładkich krawędzi) i zwraca Surface."""
    skala = 2
    R = PROMIEN * skala
    rozm = 2 * R + 8 * skala
    c = rozm // 2
    pow_ = pygame.Surface((rozm, rozm), pygame.SRCALPHA)

    n = len(pola)
    # obwódka
    pygame.draw.circle(pow_, (60, 40, 10), (c, c), R + 7 * skala)
    pygame.draw.circle(pow_, ZLOTY, (c, c), R + 5 * skala)

    if n == 0:
        pygame.draw.circle(pow_, (40, 44, 66), (c, c), R)
    else:
        kat = 360.0 / n
        kol = kolory_pol(n)
        for i in range(n):
            # kąty mierzone zgodnie z ruchem wskazówek zegara od góry
            a0, a1 = i * kat, (i + 1) * kat
            pkt = [(c, c)]
            kroki = max(4, int(kat / 1.5))
            for k in range(kroki + 1):
                a = math.radians(a0 + (a1 - a0) * k / kroki)
                pkt.append((c + R * math.sin(a), c - R * math.cos(a)))
            pygame.draw.polygon(pow_, kol[i], pkt)
        # linie podziału
        if n > 1:
            for i in range(n):
                a = math.radians(i * kat)
                pygame.draw.line(pow_, BIALY, (c, c),
                                 (c + R * math.sin(a), c - R * math.cos(a)), 3 * skala)
        # napisy
        r_tekstu_wew = 0.24 * R
        r_tekstu_zew = 0.93 * R
        max_szer = r_tekstu_zew - r_tekstu_wew
        r_srod = (r_tekstu_wew + r_tekstu_zew) / 2
        max_wys = min(2 * math.pi * r_srod / n * 0.8, 46 * skala) if n > 1 else 46 * skala
        for i, tekst in enumerate(pola):
            f, t = dopasuj_tekst(tekst, max_szer, max_wys, start=30 * skala)
            surf = f.render(t, True, (25, 25, 35))
            m = (i + 0.5) * kat
            obr = pygame.transform.rotate(surf, 90 - m)
            # środek tekstu – przy zewnętrznej krawędzi, wyrównany do prawej
            r_pos = r_tekstu_zew - surf.get_width() / 2
            mr = math.radians(m)
            x = c + r_pos * math.sin(mr)
            y = c - r_pos * math.cos(mr)
            pow_.blit(obr, obr.get_rect(center=(x, y)))
        # kołki na obwodzie
        for i in range(n):
            a = math.radians(i * kat)
            p = (c + (R - 2 * skala) * math.sin(a), c - (R - 2 * skala) * math.cos(a))
            pygame.draw.circle(pow_, (90, 70, 20), p, 6 * skala)
            pygame.draw.circle(pow_, (255, 235, 150), p, 4 * skala)

    # piasta
    pygame.draw.circle(pow_, (60, 40, 10), (c, c), int(0.13 * R))
    pygame.draw.circle(pow_, ZLOTY, (c, c), int(0.12 * R))
    pygame.draw.circle(pow_, (255, 235, 150), (c, c), int(0.06 * R))

    return pygame.transform.smoothscale(pow_, (rozm // skala, rozm // skala))


def narysuj_wskaznik(ekran, wychylenie):
    """Wskaźnik (języczek) na górze koła; 'wychylenie' w stopniach – podskakuje przy tyknięciu."""
    cx, cy = SRODEK[0], SRODEK[1] - PROMIEN - 4
    os_ = (cx, cy - 34)  # punkt obrotu
    pkt = [(-22, -44), (22, -44), (0, 18)]
    a = math.radians(wychylenie)
    obrocone = []
    for x, y in pkt:
        y2 = y + 34
        obrocone.append((os_[0] + x * math.cos(a) - y2 * math.sin(a),
                         os_[1] + x * math.sin(a) + y2 * math.cos(a)))
    cien = [(x + 3, y + 4) for x, y in obrocone]
    pygame.draw.polygon(ekran, (0, 0, 0), cien)
    pygame.draw.polygon(ekran, (230, 40, 60), obrocone)
    pygame.draw.polygon(ekran, BIALY, obrocone, 3)
    pygame.draw.circle(ekran, BIALY, os_, 9)
    pygame.draw.circle(ekran, (230, 40, 60), os_, 5)


# ---------------------------------------------------------------------
#  Gra
# ---------------------------------------------------------------------
class KoloFortuny:
    def __init__(self):
        pygame.init()
        self.dzwieki = Dzwieki()
        self.ekran = pygame.display.set_mode((SZEROKOSC, WYSOKOSC))
        pygame.display.set_caption("Koło Fortuny")
        self.zegar = pygame.time.Clock()

        self.f_tytul = czcionka(40)
        self.f_duza = czcionka(30)
        self.f_mala = czcionka(18)
        self.f_wynik = czcionka(56)

        self.reset()

    def reset(self):
        self.pola = [p for p in POLA if str(p).strip()]
        self.historia = []
        self.kat = random.uniform(0, 360)
        self.predkosc = 0.0
        self.kreci = False
        self.wynik = None  # indeks wylosowanego pola (czeka na potwierdzenie)
        self.wychylenie = 0.0
        self.przebuduj_kolo()
        self.ostatni_idx = self.idx_pod_wskaznikiem()

    def przebuduj_kolo(self):
        self.kolo_surf = narysuj_kolo(self.pola)

    def idx_pod_wskaznikiem(self):
        n = len(self.pola)
        if n == 0:
            return None
        kat_pola = 360.0 / n
        return int((self.kat % 360.0) // kat_pola) % n

    # --- akcje ---
    def zakrec(self):
        if self.kreci or self.wynik is not None or not self.pola:
            return
        self.predkosc = random.uniform(PREDKOSC_MIN, PREDKOSC_MAX)
        self.kreci = True

    def potwierdz_wynik(self):
        if self.wynik is None:
            return
        wygrane = self.pola.pop(self.wynik)
        self.historia.append(wygrane)
        self.wynik = None
        self.przebuduj_kolo()
        self.ostatni_idx = self.idx_pod_wskaznikiem()

    def przycisk_rect(self):
        return pygame.Rect(PANEL_X, WYSOKOSC - 140, 300, 80)

    def klik(self, pos):
        if self.wynik is not None:
            self.potwierdz_wynik()
            return
        dx, dy = pos[0] - SRODEK[0], pos[1] - SRODEK[1]
        if self.przycisk_rect().collidepoint(pos) or dx * dx + dy * dy <= PROMIEN * PROMIEN:
            self.zakrec()

    # --- logika ---
    def aktualizuj(self, dt):
        if self.kreci:
            self.predkosc -= (self.predkosc * TARCIE + HAMOWANIE_STALE) * dt
            if self.predkosc <= 0:
                self.predkosc = 0
                self.kreci = False
                self.wynik = self.idx_pod_wskaznikiem()
                self.dzwieki.zagraj_wygrana()
            # obrót zgodnie z ruchem wskazówek zegara
            self.kat -= self.predkosc * dt

            idx = self.idx_pod_wskaznikiem()
            if idx != self.ostatni_idx:
                self.ostatni_idx = idx
                self.dzwieki.zagraj_tyk()
                # języczek podskakuje – mocniej przy wolnym kręceniu
                self.wychylenie = -min(28.0, 10.0 + 4000.0 / max(self.predkosc, 1))
        # powrót języczka
        self.wychylenie *= math.exp(-dt * 18)

    # --- rysowanie ---
    def rysuj(self):
        e = self.ekran
        e.fill(TLO)

        # poświata pod kołem
        for r, a in ((PROMIEN + 40, 18), (PROMIEN + 25, 30)):
            s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 200, 40, a), (r, r), r)
            e.blit(s, (SRODEK[0] - r, SRODEK[1] - r))

        obr = pygame.transform.rotozoom(self.kolo_surf, self.kat, 1.0)
        e.blit(obr, obr.get_rect(center=SRODEK))
        narysuj_wskaznik(e, self.wychylenie)

        # --- panel boczny ---
        x0 = PANEL_X
        e.blit(self.f_tytul.render("KOŁO FORTUNY", True, ZLOTY), (x0, 30))
        e.blit(self.f_mala.render(f"Pozostało pól: {len(self.pola)}", True, SZARY), (x0, 90))

        e.blit(self.f_duza.render("Wylosowane:", True, BIALY), (x0, 130))
        y = 170
        pokaz = self.historia[-14:]
        start_nr = len(self.historia) - len(pokaz) + 1
        for k, h in enumerate(pokaz):
            f, t = dopasuj_tekst(f"{start_nr + k}. {h}", 320, 30, start=22)
            e.blit(f.render(t, True, (220, 220, 235)), (x0, y))
            y += 28

        # przycisk
        r = self.przycisk_rect()
        aktywny = not self.kreci and self.wynik is None and self.pola
        kol = (230, 40, 60) if aktywny else (90, 90, 110)
        pygame.draw.rect(e, (0, 0, 0), r.move(4, 5), border_radius=18)
        pygame.draw.rect(e, kol, r, border_radius=18)
        pygame.draw.rect(e, BIALY, r, 3, border_radius=18)
        napis = "KRĘĆ!" if self.pola else "KONIEC"
        t = self.f_tytul.render(napis, True, BIALY)
        e.blit(t, t.get_rect(center=r.center))
        pod = "SPACJA – kręć    R – reset    ESC – wyjście"
        t = self.f_mala.render(pod, True, SZARY)
        e.blit(t, (r.centerx - t.get_width() // 2, r.bottom + 10))

        # podświetlenie pola pod wskaźnikiem podczas kręcenia
        if self.kreci and self.pola:
            idx = self.idx_pod_wskaznikiem()
            f, t = dopasuj_tekst(self.pola[idx], 320, 40, start=30)
            s = f.render(t, True, BIALY)
            e.blit(s, (x0, WYSOKOSC - 205))

        if not self.pola and self.wynik is None:
            self.rysuj_banner("Wszystko wylosowane!", "Naciśnij R, żeby zacząć od nowa")

        if self.wynik is not None:
            self.rysuj_banner(self.pola[self.wynik], "Kliknij lub SPACJA – usuń z koła i graj dalej",
                              naglowek="WYLOSOWANO:")

        pygame.display.flip()

    def rysuj_banner(self, tekst, podpis, naglowek=None):
        e = self.ekran
        ciemne = pygame.Surface((SZEROKOSC, WYSOKOSC), pygame.SRCALPHA)
        ciemne.fill((0, 0, 0, 140))
        e.blit(ciemne, (0, 0))
        box = pygame.Rect(0, 0, 760, 250)
        box.center = (SZEROKOSC // 2, WYSOKOSC // 2)
        pygame.draw.rect(e, (30, 32, 52), box, border_radius=24)
        pygame.draw.rect(e, ZLOTY, box, 5, border_radius=24)
        y = box.top + 30
        if naglowek:
            t = self.f_duza.render(naglowek, True, ZLOTY)
            e.blit(t, t.get_rect(midtop=(box.centerx, y)))
        f, txt = dopasuj_tekst(tekst, box.width - 60, 80, start=64)
        t = f.render(txt, True, BIALY)
        e.blit(t, t.get_rect(center=(box.centerx, box.centery + 5)))
        t = self.f_mala.render(podpis, True, SZARY)
        e.blit(t, t.get_rect(midbottom=(box.centerx, box.bottom - 25)))

    # --- pętla główna ---
    def uruchom(self):
        while True:
            dt = self.zegar.tick(FPS) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return
                    if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                        if self.wynik is not None:
                            self.potwierdz_wynik()
                        else:
                            self.zakrec()
                    if ev.key == pygame.K_r and not self.kreci:
                        self.reset()
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self.klik(ev.pos)
            self.aktualizuj(dt)
            self.rysuj()


if __name__ == "__main__":
    KoloFortuny().uruchom()
    pygame.quit()
    sys.exit()
