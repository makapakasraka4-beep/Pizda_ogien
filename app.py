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
</style>
""", unsafe_allow_html=True)

# Pobieranie tajnego klucza bazy z sekretów Streamlita
try:
    DB_URI = st.secrets["DB_URI"]
except:
    st.error("Błąd: Nie skonfigurowano bazy danych w Streamlit Secrets (DB_URI).")
    st.stop()

# --- TURBO DOŁADOWANIE (CACHE) ---

@st.cache_resource
def get_db_connection():
    return psycopg2.connect(DB_URI)

@st.cache_data(ttl=600)
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (id SERIAL PRIMARY KEY, name TEXT, username TEXT, icon TEXT, color TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS plan
                 (id SERIAL PRIMARY KEY, kategoria TEXT, cwiczenie TEXT, opis TEXT, serie INTEGER, powtorzenia INTEGER, obciazenie REAL, pompa_rate INTEGER, username TEXT, masa_wlasna INTEGER DEFAULT 0, na_czas INTEGER DEFAULT 0, czas INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historia
                 (id SERIAL PRIMARY KEY, data TEXT, kategoria TEXT, cwiczenie TEXT, serie INTEGER, powtorzenia INTEGER, obciazenie REAL, pompa_rate INTEGER, punkty_pompy REAL, username TEXT, masa_wlasna INTEGER DEFAULT 0, na_czas INTEGER DEFAULT 0, czas INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pomiary
                 (id SERIAL PRIMARY KEY, data TEXT, waga REAL, username TEXT)''')

    c.execute("SELECT COUNT(*) FROM categories WHERE username = 'Główny'")
    if c.fetchone()[0] == 0:
        default_cats = [("Push", "✋", "#FF4B4B"), ("Pull", "✊", "#00CCFF"), ("Nogi", "🦵", "#00FF00")]
        for nazwa, ikona, kolor in default_cats:
            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (%s, 'Główny', %s, %s)", (nazwa, ikona, kolor))
    conn.commit()

# --- LOGIKA ---

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

    st.markdown("<h1 style='text-align: center; color: #FFD700; font-size: 3.5rem; font-weight: 900; text-transform: uppercase;'>💪 PIZDA OGIEŃ !!!</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_log, tab_reg = st.tabs(["🔒 Logowanie", "📝 Nowa Rejestracja"])
        with tab_log:
            u = st.text_input("Login", key="log_u")
            p = st.text_input("Hasło", type="password", key="log_p")
            if st.button("Wejdź", type="primary", use_container_width=True):
                conn = get_db_connection(); c = conn.cursor()
                c.execute("SELECT password FROM users WHERE username = %s", (u,))
                data = c.fetchone()
                if data and check_hashes(p, data[0]):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else: st.error("Błędny login lub hasło")
        with tab_reg:
            nu = st.text_input("Nowy Login", key="reg_u")
            np = st.text_input("Nowe Hasło", type="password", key="reg_p")
            if st.button("Zarejestruj", use_container_width=True):
                if nu and np:
                    conn = get_db_connection(); c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username = %s", (nu,))
                    if c.fetchone(): st.error("Login zajęty!")
                    else:
                        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (nu, make_hashes(np)))
                        default_cats = [("Push", "✋", "#FF4B4B"), ("Pull", "✊", "#00CCFF"), ("Nogi", "🦵", "#00FF00")]
                        for nazwa, ikona, kolor in default_cats:
                            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (%s, %s, %s, %s)", (nazwa, nu, ikona, kolor))
                        conn.commit(); st.success("Konto gotowe! Zaloguj się.")
    return False

def render_zarzadzanie_planem(kategoria_nazwa, ikona, kolor):
    usr = st.session_state.username
    conn = get_db_connection()
    df_plan = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=%s AND username=%s", conn, params=(kategoria_nazwa, usr))
    edit_key = f"edit_id_{kategoria_nazwa}_{usr}"
    if edit_key not in st.session_state: st.session_state[edit_key] = None

    st.markdown(f"<h3 style='color: {kolor};'>{ikona} Plan: {kategoria_nazwa}</h3>", unsafe_allow_html=True)
    if not df_plan.empty:
        for idx, row in df_plan.iterrows():
            c_a, c_b, c_c = st.columns([5, 0.8, 0.8], vertical_alignment="center")
            obc_part = f"Masa wł. + {row['obciazenie']}kg" if row['masa_wlasna'] and row['obciazenie'] > 0 else ("Masa wł." if row['masa_wlasna'] else f"{row['obciazenie']}kg")
            if row['na_czas'] == 1:
                c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x | ⏱️ {row['czas']}s | {obc_part}")
            else:
                c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x{row['powtorzenia']} | {obc_part}")
            with c_b:
                if st.button("Edytuj", key=f"ed_{row['id']}"): st.session_state[edit_key] = row['id']; st.rerun()
            with c_c:
                if st.button("Usuń", key=f"del_{row['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM plan WHERE id=%s", (row['id'],)); conn.commit(); st.rerun()
    else: st.info("Dodaj pierwsze ćwiczenie.")

    st.markdown("---")
    edit_id = st.session_state[edit_key]
    d_n, d_s, d_p, d_o, d_pr, d_mw, d_nc, d_cz = ("", 3, 10, 0.0, 3, 0, 0, 60)
    if edit_id:
        c = conn.cursor(); c.execute("SELECT cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, masa_wlasna, na_czas, czas FROM plan WHERE id=%s", (edit_id,))
        res = c.fetchone()
        if res: d_n, d_s, d_p, d_o, d_pr, d_mw, d_nc, d_cz = res

    with st.form(f"form_{kategoria_nazwa}", clear_on_submit=True):
        st.markdown(f"**{'Edytuj' if edit_id else 'Dodaj nowe'} ćwiczenie**")
        typ = st.radio("Typ ćwiczenia", ["Klasyczne (Ciężar + Powtórzenia)", "Na czas (Sekundy, np. Plank)"], index=1 if d_nc else 0)
        c1, c2, c3, c4, c5 = st.columns([2.5, 0.8, 1.0, 1.2, 0.8], vertical_alignment="bottom")
        nazwa = c1.text_input("Nazwa", value=d_n)
        serie = c2.number_input("Serie", min_value=1, value=int(d_s))
        powt = c3.number_input("Powt. / Sekundy", min_value=1, value=int(d_cz) if d_nc else int(d_p))
        obc = c4.number_input("Dodatkowe kg", min_value=0.0, format="%g", value=float(d_o))
        mw_bool = c5.toggle("Masa wł.", value=bool(d_mw))
        pompa = st.slider("POMPA", 1, 5, int(d_pr))
        
        if st.form_submit_button("ZAPISZ"):
            if nazwa:
                is_time = 1 if "czas" in typ else 0
                c = conn.cursor()
                if edit_id:
                    c.execute("UPDATE plan SET cwiczenie=%s, serie=%s, powtorzenia=%s, obciazenie=%s, pompa_rate=%s, masa_wlasna=%s, na_czas=%s, czas=%s WHERE id=%s", 
                              (nazwa, serie, 0 if is_time else powt, obc, pompa, int(mw_bool), is_time, powt if is_time else 0, edit_id))
                    st.session_state[edit_key] = None
                else:
                    c.execute("INSERT INTO plan (kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, masa_wlasna, na_czas, czas, username) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
                              (kategoria_nazwa, nazwa, serie, 0 if is_time else powt, obc, pompa, int(mw_bool), is_time, powt if is_time else 0, usr))
                conn.commit(); st.rerun()

def main():
    init_db()
    if not auth_screen(): return
    usr = st.session_state.username
    if 'reset_counter' not in st.session_state: st.session_state.reset_counter = 0

    st.markdown("<h1 style='text-align: center; color: #FFD700; font-size: 3rem; font-weight: 900; text-transform: uppercase;'>💪 PIZDA OGIEŃ !!!</h1>", unsafe_allow_html=True)
    conn = get_db_connection()
    categories_df = pd.read_sql_query("SELECT name, icon, color FROM categories WHERE username = %s", conn, params=(usr,))

    tabs_names = ["📋 Dzisiejszy Trening", "📈 Statystyki", "📏 Pomiary"] + [f"{row['icon']} {row['name']}" for _, row in categories_df.iterrows()] + ["⚙️ Ustawienia"]
    all_tabs = st.tabs(tabs_names)

    # 1. TRENING
    with all_tabs[0]:
        if categories_df.empty: st.warning("Stwórz plan w Ustawieniach!")
        else:
            wybrany = st.radio("Wybierz trening:", categories_df['name'].tolist(), horizontal=True)
            cat_info = categories_df[categories_df['name'] == wybrany].iloc[0]
            st.markdown(f"<h3 style='color: {cat_info['color']};'>{cat_info['icon']} {wybrany}</h3>", unsafe_allow_html=True)
            plan_df = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=%s AND username=%s", conn, params=(wybrany, usr))
            if not plan_df.empty:
                dt = st.date_input("Data", datetime.today()); zrobione = []; rc = st.session_state.reset_counter
                latest_weight = get_latest_weight(usr)
                for i, r in plan_df.iterrows():
                    c1, c2, c3, c4, c5, c6, c7 = st.columns([2.2, 0.8, 1.0, 1.0, 0.9, 1.0, 1.2], vertical_alignment="center")
                    c1.markdown(f"<div style='background-color: {cat_info['color']}33; border-left: 5px solid {cat_info['color']}; padding: 10px; border-radius: 6px; font-weight: 800;'>{r['cwiczenie']}</div>", unsafe_allow_html=True)
                    s = c2.number_input("Serie", value=int(r['serie']), key=f"s_{r['id']}_{rc}")
                    if r['na_czas'] == 1:
                        cz = c3.number_input("Sekundy", value=int(r['czas']), key=f"cz_{r['id']}_{rc}")
                        p = 0
                    else:
                        p = c3.number_input("Powt.", value=int(r['powtorzenia']), key=f"p_{r['id']}_{rc}")
                        cz = 0
                    mw = c5.toggle("Masa wł.", value=bool(r['masa_wlasna']), key=f"mw_{r['id']}_{rc}")
                    w = c4.number_input("+ Kg" if mw else "Kg", value=float(r['obciazenie']), key=f"w_{r['id']}_{rc}")
                    pompa = c6.number_input("Pompa", 1, 5, int(r['pompa_rate']), key=f"pr_{r['id']}_{rc}")
                    if c7.toggle("Zrobione", key=f"z_{r['id']}_{rc}"):
                        zrobione.append({'c': r['cwiczenie'], 's': s, 'p': p, 'w': w, 'pr': pompa, 'mw': int(mw), 'nc': int(r['na_czas']), 'cz': cz})
                if st.button("🔥 ZAPISZ TRENING 🔥", type="primary", use_container_width=True) and zrobione:
                    c = conn.cursor()
                    for z in zrobione:
                        total_w = z['w'] + (latest_weight if z['mw'] == 1 else 0)
                        val_w = total_w if total_w > 0 else 1
                        pts = z['s'] * (z['cz'] if z['nc'] else z['p']) * val_w * z['pr']
                        c.execute("INSERT INTO historia (data, kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, punkty_pompy, masa_wlasna, na_czas, czas, username) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                  (str(dt), wybrany, z['c'], z['s'], z['p'], z['w'], z['pr'], pts, z['mw'], z['nc'], z['cz'], usr))
                        c.execute("UPDATE plan SET serie=%s, powtorzenia=%s, obciazenie=%s, pompa_rate=%s, masa_wlasna=%s, na_czas=%s, czas=%s WHERE cwiczenie=%s AND kategoria=%s AND username=%s",
                                  (z['s'], z['p'], z['w'], z['pr'], z['mw'], z['nc'], z['cz'], z['c'], wybrany, usr))
                    conn.commit(); st.session_state.reset_counter += 1; st.rerun()

    # 2. STATYSTYKI
    with all_tabs[1]:
        hist = pd.read_sql_query("SELECT * FROM historia WHERE username=%s ORDER BY data DESC", conn, params=(usr,))
        if not hist.empty:
            wykres_df = hist.groupby(['data', 'kategoria'])['punkty_pompy'].sum().reset_index()
            st.plotly_chart(px.bar(wykres_df, x='data', y='punkty_pompy', color='kategoria', title="🔥 Suma punktów pompy"), use_container_width=True)
            for d_str in hist['data'].unique():
                df_day = hist[hist['data'] == d_str]
                with st.expander(f"🗓️ {d_str} | 🔥 {df_day['punkty_pompy'].sum()} pkt"):
                    for _, r in df_day.iterrows():
                        st.write(f"🗑️ {r['cwiczenie']} - {r['serie']}x{r['powtorzenia'] if not r['na_czas'] else str(r['czas'])+'s'} | {r['obciazenie']}kg")
                        if st.button("Usuń", key=f"delh_{r['id']}"):
                            c = conn.cursor(); c.execute("DELETE FROM historia WHERE id=%s", (r['id'],)); conn.commit(); st.rerun()

    # 3. POMIARY
    with all_tabs[2]:
        with st.form("pomiar"):
            d_p = st.date_input("Data"); w_p = st.number_input("Waga (kg)", 30.0, 200.0, 80.0)
            if st.form_submit_button("DODAJ"):
                c = conn.cursor(); c.execute("INSERT INTO pomiary (data, waga, username) VALUES (%s,%s,%s)", (str(d_p), w_p, usr)); conn.commit(); st.rerun()
        p_df = pd.read_sql_query("SELECT * FROM pomiary WHERE username=%s ORDER BY data ASC", conn, params=(usr,))
        if not p_df.empty: st.plotly_chart(px.line(p_df, x='data', y='waga', markers=True), use_container_width=True)

    # RESZTA (PLANY I USTAWIENIA)
    for i, row in categories_df.iterrows():
        with all_tabs[3 + i]: render_zarzadzanie_planem(row['name'], row['icon'], row['color'])

    with all_tabs[-1]:
        st.subheader("⚙️ Zarządzaj Planami")
        with st.form("new_cat"):
            n_c = st.text_input("Nazwa planu"); i_c = st.selectbox("Ikona", ["🏋️", "💪", "🔥", "🏃"]); c_c = st.color_picker("Kolor", "#FFD700")
            if st.form_submit_button("DODAJ"):
                c = conn.cursor(); c.execute("INSERT INTO categories (name, username, icon, color) VALUES (%s,%s,%s,%s)", (n_c, usr, i_c, c_c)); conn.commit(); st.rerun()
        for _, r in categories_df.iterrows():
            if st.button(f"Usuń {r['name']}", key=f"dc_{r['name']}"):
                c = conn.cursor(); c.execute("DELETE FROM categories WHERE name=%s AND username=%s", (r['name'], usr)); conn.commit(); st.rerun()

if __name__ == "__main__": main()
