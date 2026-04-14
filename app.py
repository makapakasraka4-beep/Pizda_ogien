import streamlit as st
import pandas as pd
import psycopg2
import hashlib
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Mój Trening", page_icon="💪", layout="wide")

# ----- MAGIA CSS -----
st.markdown("""
<style>
/* Zmniejszenie bocznych marginesów na małych ekranach, żeby nie marnować cennego miejsca */
.block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    max-width: 100vw !important;
    overflow-x: hidden !important;
}

div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:nth-child(odd) {
    background-color: rgba(255, 255, 255, 0.02);
    border-radius: 12px;
    padding: 10px 5px;
    margin-bottom: 5px;
}
div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:nth-child(even) {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 12px;
    padding: 10px 5px;
    margin-bottom: 5px;
}
.zrobione-text {
    color: #00ff00;
    text-shadow: 0px 0px 8px rgba(0,255,0,0.4);
    font-weight: 900;
}

/* --- OPTYMALIZACJA STRICTE POD TELEFON (MOBILE FIRST) --- */
input[type="number"], input[type="text"] {
    font-size: 16px !important; /* Blokuje automatyczne zoomowanie ekranu na iOS */
}
button {
    min-height: 44px !important; 
}

/* Ujednolicony, nowoczesny design ramek (Expander) */
div[data-testid="stExpander"] {
    border: 1px solid rgba(255, 255, 255, 0.1) !important; 
    border-radius: 10px !important;
    background-color: rgba(255, 255, 255, 0.03) !important; 
    overflow: hidden !important; 
    margin-bottom: 0 !important;
}
div[data-testid="stExpander"] summary {
    background-color: rgba(0, 0, 0, 0.2) !important; 
    padding: 12px 10px !important; 
}
div[data-testid="stExpander"] summary p {
    font-weight: 900 !important;
    font-size: 15px !important; 
    line-height: 1.2 !important;
    color: #ffffff !important; 
}
div[data-testid="stExpander"] summary svg {
    color: #ffffff !important; 
}

/* --- PERFEKCYJNE WYRÓWNANIE W RZĘDZIE NA TELEFONACH (FLEXBOX) --- */
@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) {
        display: flex !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
        gap: 8px !important;
    }
    /* Lewa strona z ćwiczeniem zajmuje tyle miejsca, ile to możliwe */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) > div[data-testid="column"]:nth-child(1) {
        flex: 1 1 auto !important;
        width: auto !important;
        min-width: 0 !important; 
    }
    /* Prawa strona z przełącznikiem zajmuje tylko niezbędne minimum */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) > div[data-testid="column"]:nth-child(2) {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: fit-content !important;
    }
}
</style>
""", unsafe_allow_html=True)

# Pobieranie tajnego klucza bazy
try:
    DB_URI = st.secrets["DB_URI"]
except:
    st.error("Błąd: Nie skonfigurowano bazy danych w Streamlit Secrets (DB_URI).")
    st.stop()


# --- TURBO DOŁADOWANIE (CACHE) ---
@st.cache_resource(validate=lambda conn: conn.closed == 0)
def get_db_connection():
    return psycopg2.connect(DB_URI)


@st.cache_data(ttl=600)
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (id SERIAL PRIMARY KEY, name TEXT, username TEXT, icon TEXT, color TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS plan (
                    id SERIAL PRIMARY KEY, kategoria TEXT, cwiczenie TEXT, opis TEXT,
                    serie INTEGER, powtorzenia INTEGER, obciazenie REAL, pompa_rate INTEGER,
                    username TEXT, masa_wlasna INTEGER DEFAULT 0, na_czas INTEGER DEFAULT 0, czas INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historia (
                    id SERIAL PRIMARY KEY, data TEXT, kategoria TEXT, cwiczenie TEXT,
                    serie INTEGER, powtorzenia INTEGER, obciazenie REAL, pompa_rate INTEGER,
                    punkty_pompy REAL, username TEXT, masa_wlasna INTEGER DEFAULT 0, na_czas INTEGER DEFAULT 0, czas INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pomiary (id SERIAL PRIMARY KEY, data TEXT, waga REAL, username TEXT)''')

    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='plan' AND column_name='kolejnosc'")
    if not c.fetchone():
        c.execute("ALTER TABLE plan ADD COLUMN kolejnosc INTEGER DEFAULT 0")
        c.execute("UPDATE plan SET kolejnosc = id") 
        conn.commit()

    c.execute("SELECT COUNT(*) FROM categories WHERE username = 'Główny'")
    if c.fetchone()[0] == 0:
        default_cats = [("Push", "✋", "#FF4B4B"), ("Pull", "✊", "#00CCFF"), ("Nogi", "🦵", "#00FF00")]
        for nazwa, ikona, kolor in default_cats:
            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (%s, 'Główny', %s, %s)",
                      (nazwa, ikona, kolor))

    conn.commit()


# --- LOGIKA APLIKACJI ---

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def get_latest_weight(usr):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT waga FROM pomiary WHERE username=%s ORDER BY data DESC LIMIT 1", (usr,))
    res = c.fetchone()
    return res[0] if res else 0.0


def auth_screen():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    if st.session_state.logged_in:
        with st.sidebar:
            st.success(f"👤 Profil: **{st.session_state.username}**")
            if st.button("Wyloguj się"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
        return True

    st.markdown(
        "<h1 style='text-align: center; color: #FFD700; font-size: 3.5rem; font-weight: 900; text-transform: uppercase;'>💪 PIZDA OGIEŃ !!!</h1>",
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_log, tab_reg = st.tabs(["🔒 Logowanie", "📝 Nowa Rejestracja"])
        with tab_log:
            u = st.text_input("Login", key="log_u")
            p = st.text_input("Hasło", type="password", key="log_p")
            if st.button("Wejdź", type="primary", use_container_width=True):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT password FROM users WHERE username = %s", (u,))
                data = c.fetchone()
                if data and check_hashes(p, data[0]):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło")
        with tab_reg:
            nu = st.text_input("Nowy Login", key="reg_u")
            np = st.text_input("Nowe Hasło", type="password", key="reg_p")
            if st.button("Zarejestruj", use_container_width=True):
                if nu and np:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username = %s", (nu,))
                    if c.fetchone():
                        st.error("Login zajęty!")
                    else:
                        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (nu, make_hashes(np)))
                        default_cats = [("Push", "✋", "#FF4B4B"), ("Pull", "✊", "#00CCFF"), ("Nogi", "🦵", "#00FF00")]
                        for nazwa, ikona, kolor in default_cats:
                            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (%s, %s, %s, %s)",
                                      (nazwa, nu, ikona, kolor))
                        conn.commit()
                        st.success("Konto gotowe! Zaloguj się.")
    return False



def render_zarzadzanie_planem(cat_id, kategoria_nazwa, ikona, kolor):
    usr = st.session_state.username
    conn = get_db_connection()
    
    df_plan = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=%s AND username=%s ORDER BY kolejnosc ASC, id ASC", conn, params=(kategoria_nazwa, usr))

    edit_key = f"edit_id_{cat_id}_{usr}"
    if edit_key not in st.session_state: st.session_state[edit_key] = None

    st.markdown(f"<h3 style='color: {kolor}; margin-bottom: 0px;'>{ikona} Edytujesz Plan: {kategoria_nazwa}</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_plan.empty:
        for idx, row in df_plan.iterrows():
            c_a, c_ord, c_b, c_c = st.columns([4.2, 1.0, 0.8, 0.8], vertical_alignment="center")
            
            if row['na_czas'] == 1:
                obc_str = f"{row['czas']} sekund"
                c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x | ⏱️ {obc_str}")
            else:
                obc_str = f"Masa wł. + {row['obciazenie']}kg" if row['masa_wlasna'] and row['obciazenie'] > 0 else (
                    "Masa wł." if row['masa_wlasna'] else f"{row['obciazenie']}kg")
                c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x{row['powtorzenia']} | {obc_str}")

            with c_ord:
                st.number_input("Nr", value=int(row['kolejnosc']), step=1, key=f"ord_{row['id']}", label_visibility="collapsed")

            with c_b:
                if st.button("Edytuj", key=f"ed_{row['id']}"):
                    st.session_state[edit_key] = row['id']
                    st.rerun()
            with c_c:
                if st.button("Usuń", key=f"del_{row['id']}"):
                    c = conn.cursor()
                    c.execute("DELETE FROM plan WHERE id=%s", (row['id'],))
                    conn.commit()
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 ZAPISZ KOLEJNOŚĆ", type="secondary", key=f"save_ord_{cat_id}", use_container_width=True):
            c = conn.cursor()
            czy_zmieniono = False
            for idx, row in df_plan.iterrows():
                nowa_kol = st.session_state[f"ord_{row['id']}"]
                if nowa_kol != int(row['kolejnosc']):
                    c.execute("UPDATE plan SET kolejnosc=%s WHERE id=%s", (nowa_kol, row['id']))
                    czy_zmieniono = True
            
            if czy_zmieniono:
                conn.commit()
                st.rerun()

    else:
        st.info("Dodaj pierwsze ćwiczenie do tego planu.")

    st.markdown("---")
    edit_id = st.session_state[edit_key]
    d_n, d_s, d_p, d_o, d_pr, d_mw, d_nc, d_cz = ("", 3, 10, 0.0, 3, 0, 0, 60)
    if edit_id:
        c = conn.cursor()
        c.execute(
            "SELECT cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, masa_wlasna, na_czas, czas FROM plan WHERE id=%s",
            (edit_id,))
        res = c.fetchone()
        if res: d_n, d_s, d_p, d_o, d_pr, d_mw, d_nc, d_cz = res

    with st.form(f"form_{cat_id}", clear_on_submit=True):
        st.markdown(f"**{'Edytuj' if edit_id else 'Dodaj nowe'} ćwiczenie**")
        typ = st.radio("Typ ćwiczenia", ["Klasyczne (Ciężar + Powtórzenia)", "Na czas (Sekundy, np. Plank)"],
                       index=1 if d_nc else 0)

        c1, c2, c3, c4, c5 = st.columns([2.5, 0.8, 1.0, 1.2, 0.8], vertical_alignment="bottom")
        nazwa = c1.text_input("Nazwa", value=d_n)
        serie = c2.number_input("Serie", min_value=1, value=int(d_s))

        powt = c3.number_input("Powt. / Czas(s)", min_value=1, value=int(d_cz) if d_nc else int(d_p),
                               help="Tu wpisz powtórzenia lub sekundy")
        mw_bool = c5.toggle("Masa wł.", value=bool(d_mw))
        obc = c4.number_input("Dodatkowe kg / Zignoruj", min_value=0.0, format="%g", value=float(d_o))

        pompa = st.slider("POMPA", 1, 5, int(d_pr))

        if st.form_submit_button("ZAPISZ"):
            if nazwa:
                is_time = 1 if "czas" in typ else 0
                final_p = powt if not is_time else 0
                final_cz = powt if is_time else 0
                final_o = obc if not is_time else 0.0
                final_mw = int(mw_bool) if not is_time else 0

                c = conn.cursor()
                if edit_id:
                    c.execute(
                        "UPDATE plan SET cwiczenie=%s, serie=%s, powtorzenia=%s, obciazenie=%s, pompa_rate=%s, masa_wlasna=%s, na_czas=%s, czas=%s WHERE id=%s",
                        (nazwa, serie, final_p, final_o, pompa, final_mw, is_time, final_cz, edit_id))
                    st.session_state[edit_key] = None
                else:
                    c.execute("SELECT MAX(kolejnosc) FROM plan WHERE kategoria=%s AND username=%s", (kategoria_nazwa, usr))
                    res_max = c.fetchone()
                    next_k = (res_max[0] + 1) if res_max[0] is not None else 0

                    c.execute(
                        "INSERT INTO plan (kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, masa_wlasna, na_czas, czas, username, kolejnosc) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (kategoria_nazwa, nazwa, serie, final_p, final_o, pompa, final_mw, is_time, final_cz, usr, next_k))
                conn.commit()
                st.rerun()
    if edit_id:
        if st.button("Anuluj edycję"): st.session_state[edit_key] = None; st.rerun()


def main():
    init_db()
    if not auth_screen(): return
    usr = st.session_state.username

    conn = get_db_connection()
    categories_df = pd.read_sql_query("SELECT id, name, icon, color FROM categories WHERE username = %s ORDER BY id ASC", conn,
                                      params=(usr,))

    # Reset countery dla każdej kategorii by chronić stan przy zapisie
    for _, row in categories_df.iterrows():
        rc_key = f"rc_{row['name']}"
        if rc_key not in st.session_state:
            st.session_state[rc_key] = 0

    st.markdown(
        "<h1 style='text-align: center; color: #FFD700; font-size: 3rem; font-weight: 900; text-transform: uppercase;'>💪 PIZDA OGIEŃ !!!</h1>",
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    tabs_names = ["📋 Dzisiejszy Trening", "📈 Statystyki", "📏 Pomiary", "⚙️ Ustawienia Planów"]
    all_tabs = st.tabs(tabs_names)

    # 1. DZISIEJSZY TRENING
    with all_tabs[0]:
        if categories_df.empty:
            st.warning("Stwórz pierwszy plan w Ustawieniach!")
        else:
            dt = st.date_input("Wybierz Datę Treningu", datetime.today())
            st.markdown("<br>", unsafe_allow_html=True)
            
            cat_names_with_icons = [f"{r['icon']} {r['name']}" for _, r in categories_df.iterrows()]
            dzisiejszy_tabs = st.tabs(cat_names_with_icons)

            for i, cat_row in categories_df.iterrows():
                with dzisiejszy_tabs[i]:
                    wybrany = cat_row['name']
                    ikona = cat_row['icon']
                    kolor = cat_row['color']
                    
                    rc = st.session_state[f"rc_{wybrany}"]

                    # Nadanie kolorów nagłówkowi i delikatnej poświaty dla ramek ćwiczeń z danej kategorii
                    hex_c = kolor.lstrip('#')
                    if len(hex_c) == 6:
                        r, g, b = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
                        bg_rgba = f"rgba({r}, {g}, {b}, 0.15)"
                    else:
                        bg_rgba = "rgba(255, 255, 255, 0.1)"

                    st.markdown(f"""
                    <style>
                    /* Pokolorowanie konkretnej zakładki dla czytelności */
                    div[data-testid="stTabs"] button[data-baseweb="tab"]:nth-child({i+1})[aria-selected="true"] {{
                        border-bottom-color: {kolor} !important;
                    }}
                    </style>
                    """, unsafe_allow_html=True)

                    st.markdown(f"<h3 style='color: {kolor}; margin-bottom: 0px;'>{ikona} Trening: {wybrany}</h3>", unsafe_allow_html=True)
                    st.markdown("---")

                    plan_df = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=%s AND username=%s ORDER BY kolejnosc ASC, id ASC", conn, params=(wybrany, usr))
                    
                    if plan_df.empty:
                        st.info("Ten plan jest pusty. Dodaj ćwiczenia w Ustawieniach Planów.")
                    else:
                        zrobione = []

                        latest_weight = get_latest_weight(usr)
                        if plan_df['masa_wlasna'].any() and latest_weight == 0.0:
                            st.warning("⚠️ Masz ćwiczenia z masą własną, ale nie uzupełniłeś zakładki Pomiary. System policzy wagę ciała jako 0 kg.")

                        for idx, r_row in plan_df.iterrows():
                            # Wąski kontener na flexboxie z CSS-a wyżej
                            col_expander, col_done = st.columns([3, 1], vertical_alignment="center")

                            with col_expander:
                                if r_row['na_czas'] == 1:
                                    header_text = f"🏋️ {r_row['cwiczenie']} | {int(r_row['serie'])}x | ⏱️ {int(r_row['czas'])} s"
                                else:
                                    waga_str = f"Wł. + {r_row['obciazenie']:g}kg" if r_row['masa_wlasna'] and r_row['obciazenie'] > 0 else (
                                        "Masa wł." if r_row['masa_wlasna'] else f"{r_row['obciazenie']:g}kg")
                                    header_text = f"🏋️ {r_row['cwiczenie']} | {int(r_row['serie'])}x{int(r_row['powtorzenia'])} | {waga_str}"

                                with st.expander(header_text):
                                    if r_row['na_czas'] == 1:
                                        c_in1, c_in2 = st.columns(2)
                                        s = c_in1.number_input("Serie", value=int(r_row['serie']), key=f"s_{r_row['id']}_{rc}")
                                        cz = c_in2.number_input("Czas (s)", value=int(r_row['czas']), key=f"cz_{r_row['id']}_{rc}")
                                        pompa = st.number_input("Pompa (1-5)", 1, 5, int(r_row['pompa_rate']), key=f"pr_{r_row['id']}_{rc}")
                                        p, w, mw = 0, 0.0, 0
                                    else:
                                        c_in1, c_in2 = st.columns(2)
                                        s = c_in1.number_input("Serie", value=int(r_row['serie']), key=f"s_{r_row['id']}_{rc}")
                                        p = c_in2.number_input("Powt.", value=int(r_row['powtorzenia']), key=f"p_{r_row['id']}_{rc}")
                                        
                                        c_in3, c_in4 = st.columns(2, vertical_alignment="bottom")
                                        mw = c_in3.toggle("Masa wł.", value=bool(r_row['masa_wlasna']), key=f"mw_{r_row['id']}_{rc}")
                                        w = c_in4.number_input("+ Kg" if mw else "Kg", value=float(r_row['obciazenie']), key=f"w_{r_row['id']}_{rc}")
                                        
                                        pompa = st.number_input("Pompa (1-5)", 1, 5, int(r_row['pompa_rate']), key=f"pr_{r_row['id']}_{rc}")
                                        cz = 0

                            with col_done:
                                if st.toggle("Zrobione", key=f"z_{r_row['id']}_{rc}"):
                                    zrobione.append({'c': r_row['cwiczenie'], 's': s, 'p': p, 'w': w, 'pr': pompa, 'mw': int(mw), 'nc': int(r_row['na_czas']), 'cz': cz})
                            
                            st.markdown("<hr style='margin: 0.2em 0px; opacity: 0.1;'>", unsafe_allow_html=True)

                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button(f"🔥 ZAPISZ TRENING: {wybrany.upper()} 🔥", type="primary", use_container_width=True, key=f"save_btn_{wybrany}"):
                            if zrobione:
                                c = conn.cursor()
                                for z in zrobione:
                                    if z['nc'] == 1:
                                        pts = z['s'] * z['cz'] * z['pr']
                                    else:
                                        total_weight = z['w']
                                        if z['mw'] == 1: total_weight += latest_weight
                                        w_c = total_weight if total_weight > 0 else 1
                                        pts = z['s'] * z['p'] * w_c * z['pr']

                                    c.execute(
                                        "INSERT INTO historia (data, kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, punkty_pompy, masa_wlasna, na_czas, czas, username) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (str(dt), wybrany, z['c'], z['s'], z['p'], z['w'], z['pr'], pts, z['mw'], z['nc'], z['cz'], usr))
                                    
                                    c.execute(
                                        "UPDATE plan SET serie=%s, powtorzenia=%s, obciazenie=%s, pompa_rate=%s, masa_wlasna=%s, na_czas=%s, czas=%s WHERE cwiczenie=%s AND kategoria=%s AND username=%s",
                                        (z['s'], z['p'], z['w'], z['pr'], z['mw'], z['nc'], z['cz'], z['c'], wybrany, usr))
                                
                                conn.commit()
                                st.session_state[f"rc_{wybrany}"] += 1
                                st.rerun()

    # 2. STATYSTYKI
    with all_tabs[1]:
        hist = pd.read_sql_query("SELECT * FROM historia WHERE username=%s ORDER BY data DESC", conn, params=(usr,))
        
        if not hist.empty:
            # --- SEKCJA: PROGRES POSZCZEGÓLNYCH ĆWICZEŃ ---
            st.markdown("### 📈 Progres w ćwiczeniach")
            
            hist_cats = hist['kategoria'].unique().tolist()
            if hist_cats:
                kol_stat1, kol_stat2 = st.columns(2)
                wybrana_kat_stat = kol_stat1.selectbox("Wybierz plan do analizy:", hist_cats)
                
                hist_cw_filtered = hist[hist['kategoria'] == wybrana_kat_stat]
                cwiczenia_w_kat = hist_cw_filtered['cwiczenie'].unique().tolist()
                
                wybrane_cw_stat = kol_stat2.selectbox("Wybierz ćwiczenie:", cwiczenia_w_kat)
                
                if wybrane_cw_stat:
                    df_chart = hist_cw_filtered[hist_cw_filtered['cwiczenie'] == wybrane_cw_stat].copy()
                    is_time_based = df_chart['na_czas'].iloc[0] == 1
                    
                    if is_time_based:
                        # Maksymalny czas danego dnia
                        df_plot = df_chart.groupby('data')['czas'].max().reset_index()
                        df_plot = df_plot.sort_values('data')
                        fig_prog = px.line(df_plot, x='data', y='czas', markers=True, title=f"Najlepszy czas: {wybrane_cw_stat} (sekundy)")
                        fig_prog.update_traces(line_color="#00CCFF")
                        fig_prog.update_layout(yaxis_title="Czas [s]", xaxis_title="")
                    else:
                        # Maksymalne obciążenie danego dnia
                        df_plot = df_chart.groupby('data')['obciazenie'].max().reset_index()
                        df_plot = df_plot.sort_values('data')
                        fig_prog = px.line(df_plot, x='data', y='obciazenie', markers=True, title=f"Największe obciążenie: {wybrane_cw_stat} (kg)")
                        fig_prog.update_traces(line_color="#FF4B4B")
                        fig_prog.update_layout(yaxis_title="Obciążenie dodane [kg]", xaxis_title="")
                        
                    st.plotly_chart(fig_prog, use_container_width=True)

            st.markdown("---")
            # --- SEKCJA: SUMA POMPY ---
            wykres_df = hist.groupby(['data', 'kategoria'])['punkty_pompy'].sum().reset_index()
            color_map = dict(zip(categories_df['name'], categories_df['color']))
            fig = px.bar(wykres_df, x='data', y='punkty_pompy', color='kategoria', color_discrete_map=color_map,
                         title="🔥 Suma punktów pompy w dniach")
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            # --- SEKCJA: HISTORIA TRENINGÓW ---
            st.markdown("### 📅 Historia Twoich Treningów")
            unique_dates = hist['data'].unique()
            for d_str in unique_dates:
                df_day = hist[hist['data'] == d_str]
                cats_of_day = ", ".join(df_day['kategoria'].unique())
                suma_pompy_dnia = df_day['punkty_pompy'].sum()
                try:
                    d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                    d_format = d_obj.strftime("%d.%m.%Y")
                except ValueError:
                    d_format = d_str

                with st.expander(f"🗓️ {d_format} | Trening: {cats_of_day} | 🔥 Pompa: {suma_pompy_dnia}"):
                    display_df = df_day[
                        ['cwiczenie', 'serie', 'powtorzenia', 'obciazenie', 'masa_wlasna', 'na_czas', 'czas']].copy()

                    def format_obc(row):
                        if row['na_czas'] == 1: return f"⏱️ {row['czas']}s"
                        if row['masa_wlasna'] == 1: return f"Masa wł. + {row['obciazenie']}kg" if row['obciazenie'] > 0 else "Masa wł."
                        return f"{row['obciazenie']}kg"

                    display_df['Obciążenie/Czas'] = display_df.apply(format_obc, axis=1)
                    st.dataframe(display_df[['cwiczenie', 'serie', 'powtorzenia', 'Obciążenie/Czas']], hide_index=True,
                                 use_container_width=True)
                    
                    for i, r in df_day.iterrows():
                        if st.button(f"Usuń ćwiczenie: {r['cwiczenie']}", key=f"dh_{r['id']}"):
                            c = conn.cursor()
                            c.execute("DELETE FROM historia WHERE id=%s", (r['id'],))
                            conn.commit()
                            st.rerun()

                    st.markdown("<hr style='margin: 1em 0px;'>", unsafe_allow_html=True)
                    if st.toggle("🔓 Odblokuj usuwanie całego treningu z tego dnia", key=f"unlock_{d_str}"):
                        if st.button("🚨 USUŃ CAŁY TRENING", type="primary", use_container_width=True, key=f"del_all_{d_str}"):
                            c = conn.cursor()
                            c.execute("DELETE FROM historia WHERE data=%s AND username=%s", (d_str, usr))
                            conn.commit()
                            st.rerun()
        else:
            st.info("Brak historii treningów.")

    # 3. POMIARY
    with all_tabs[2]:
        with st.form("pomiar"):
            c1, c2 = st.columns(2)
            d_p = c1.date_input("Data")
            w_p = c2.number_input("Waga (kg)", 30.0, 200.0, 80.0, 0.1)
            if st.form_submit_button("DODAJ"):
                c = conn.cursor()
                c.execute("INSERT INTO pomiary (data, waga, username) VALUES (%s,%s,%s)", (str(d_p), w_p, usr))
                conn.commit()
                st.rerun()
        p_df = pd.read_sql_query("SELECT * FROM pomiary WHERE username=%s ORDER BY data ASC", conn, params=(usr,))
        if not p_df.empty: st.plotly_chart(
            px.line(p_df, x='data', y='waga', markers=True, color_discrete_sequence=['#FFD700']),
            use_container_width=True)

    # 4. USTAWIENIA PLANÓW
    with all_tabs[3]:
        st.markdown("## ⚙️ Ustawienia i Zarządzanie")
        
        opcje_menu = ["🗂️ Zarządzaj Kategoriami (Dodaj / Usuń Plan)"] + [f"{r['icon']} {r['name']}" for _, r in categories_df.iterrows()]
        wybor_edycji = st.selectbox("Wybierz co chcesz edytować:", opcje_menu)
        
        st.markdown("---")

        if wybor_edycji == "🗂️ Zarządzaj Kategoriami (Dodaj / Usuń Plan)":
            edit_cat_key = f"edit_cat_{usr}"
            if edit_cat_key not in st.session_state: st.session_state[edit_cat_key] = None
            edit_cat_name = st.session_state[edit_cat_key]
            d_cat_name, d_cat_icon, d_cat_color = ("", "🏋️", "#FFD700")
            
            if edit_cat_name:
                cat_data = categories_df[categories_df['name'] == edit_cat_name].iloc[0]
                d_cat_name, d_cat_icon, d_cat_color = cat_data['name'], cat_data['icon'], cat_data['color']

            st.subheader("⚙️ " + ("Edytuj plan" if edit_cat_name else "Dodaj nowy plan"))
            with st.form("cat_form", clear_on_submit=True):
                col_1, col_2, col_3 = st.columns([3, 1, 1])
                new_cat_name = col_1.text_input("Nazwa planu", value=d_cat_name)
                ikony_do_wyboru = ["🏋️", "🏃", "💪", "🦵", "✋", "✊", "🧘", "🚲", "🔥", "🦍", "🦖", "🏆"]
                new_cat_icon = col_2.selectbox("Ikona", ikony_do_wyboru, index=ikony_do_wyboru.index(
                    d_cat_icon) if d_cat_icon in ikony_do_wyboru else 0)
                new_cat_color = col_3.color_picker("Kolor", d_cat_color)
                if st.form_submit_button("💾 ZAPISZ KATEGORIĘ"):
                    if new_cat_name:
                        c = conn.cursor()
                        if edit_cat_name:
                            c.execute("UPDATE categories SET name=%s, icon=%s, color=%s WHERE name=%s AND username=%s",
                                      (new_cat_name, new_cat_icon, new_cat_color, edit_cat_name, usr))
                            c.execute("UPDATE plan SET kategoria=%s WHERE kategoria=%s AND username=%s",
                                      (new_cat_name, edit_cat_name, usr))
                            c.execute("UPDATE historia SET kategoria=%s WHERE kategoria=%s AND username=%s",
                                      (new_cat_name, edit_cat_name, usr))
                            st.session_state[edit_cat_key] = None
                        else:
                            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (%s, %s, %s, %s)",
                                      (new_cat_name, usr, new_cat_icon, new_cat_color))
                        conn.commit()
                        st.rerun()

            for idx, row in categories_df.iterrows():
                c_1, c_2, c_3 = st.columns([3, 0.8, 0.8], vertical_alignment="center")
                c_1.write(f"{row['icon']} {row['name']}")
                if c_2.button("Edytuj", key=f"ecat_{row['id']}"): 
                    st.session_state[edit_cat_key] = row['name']
                    st.rerun()
                if c_3.button("Usuń", key=f"del_cat_{row['id']}"):
                    c = conn.cursor()
                    c.execute("DELETE FROM categories WHERE id=%s", (row['id'],))
                    conn.commit()
                    st.rerun()
        
        else:
            for idx, row in categories_df.iterrows():
                if f"{row['icon']} {row['name']}" == wybor_edycji:
                    render_zarzadzanie_planem(row['id'], row['name'], row['icon'], row['color'])
                    break

if __name__ == "__main__": main()
