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
/* Wygląd wierszy w starszych częściach aplikacji */
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

/* --- WYMUSZENIE PRZYCISKU "ZROBIONE" OBOK EXPANDERA NA TELEFONIE --- */
@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) {
        display: flex !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) > div[data-testid="column"] {
        min-width: 0 !important;
        width: auto !important;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) > div[data-testid="column"]:nth-child(1) {
        flex: 1 1 75% !important;
        width: 75% !important;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stExpander"]) > div[data-testid="column"]:nth-child(2) {
        flex: 1 1 25% !important;
        width: 25% !important;
        display: flex;
        justify-content: flex-end; 
    }
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
    c.execute('''CREATE TABLE IF NOT EXISTS plan (
                    id SERIAL PRIMARY KEY, kategoria TEXT, cwiczenie TEXT, opis TEXT,
                    serie INTEGER, powtorzenia INTEGER, obciazenie REAL, pompa_rate INTEGER,
                    username TEXT, masa_wlasna INTEGER DEFAULT 0, na_czas INTEGER DEFAULT 0, czas INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historia (
                    id SERIAL PRIMARY KEY, data TEXT, kategoria TEXT, cwiczenie TEXT,
                    serie INTEGER, powtorzenia INTEGER, obciazenie REAL, pompa_rate INTEGER,
                    punkty_pompy REAL, username TEXT, masa_wlasna INTEGER DEFAULT 0, na_czas INTEGER DEFAULT 0, czas INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pomiary (id SERIAL PRIMARY KEY, data TEXT, waga REAL, username TEXT)''')

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


def render_zarzadzanie_planem(kategoria_nazwa, ikona, kolor):
    usr = st.session_state.username
    conn = get_db_connection()
    df_plan = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=%s AND username=%s", conn,
                                params=(kategoria_nazwa, usr))

    edit_key = f"edit_id_{kategoria_nazwa}_{usr}"
    if edit_key not in st.session_state: st.session_state[edit_key] = None

    st.markdown(f"<h3 style='color: {kolor};'>{ikona} Plan: {kategoria_nazwa}</h3>", unsafe_allow_html=True)

    if not df_plan.empty:
        for idx, row in df_plan.iterrows():
            c_a, c_b, c_c = st.columns([5, 0.8, 0.8], vertical_alignment="center")
            if row['na_czas'] == 1:
                obc_str = f"{row['czas']} sekund"
                c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x | ⏱️ {obc_str}")
            else:
                obc_str = f"Masa wł. + {row['obciazenie']}kg" if row['masa_wlasna'] and row['obciazenie'] > 0 else (
                    "Masa wł." if row['masa_wlasna'] else f"{row['obciazenie']}kg")
                c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x{row['powtorzenia']} | {obc_str}")

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

    with st.form(f"form_{kategoria_nazwa}", clear_on_submit=True):
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
                    c.execute(
                        "INSERT INTO plan (kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, masa_wlasna, na_czas, czas, username) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (kategoria_nazwa, nazwa, serie, final_p, final_o, pompa, final_mw, is_time, final_cz, usr))
                conn.commit()
                st.rerun()
    if edit_id:
        if st.button("Anuluj edycję"): st.session_state[edit_key] = None; st.rerun()


def main():
    init_db()
    if not auth_screen(): return
    usr = st.session_state.username
    if 'reset_counter' not in st.session_state: st.session_state.reset_counter = 0

    st.markdown(
        "<h1 style='text-align: center; color: #FFD700; font-size: 3rem; font-weight: 900; text-transform: uppercase;'>💪 PIZDA OGIEŃ !!!</h1>",
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    conn = get_db_connection()
    categories_df = pd.read_sql_query("SELECT name, icon, color FROM categories WHERE username = %s", conn,
                                      params=(usr,))

    cat_tabs_names = [f"{row['icon']} {row['name']}" for _, row in categories_df.iterrows()]
    tabs_names = ["📋 Dzisiejszy Trening", "📈 Statystyki", "📏 Pomiary"] + cat_tabs_names + ["⚙️ Ustawienia Planów"]
    all_tabs = st.tabs(tabs_names)

    # 1. DZISIEJSZY TRENING
    with all_tabs[0]:
        if categories_df.empty:
            st.warning("Stwórz pierwszy plan w Ustawieniach!")
        else:
            lista_kategorii = categories_df['name'].tolist()
            wybrany = st.radio("Wybierz trening:", lista_kategorii, horizontal=True)

            wybrane_dane = categories_df[categories_df['name'] == wybrany].iloc[0]
            ikona, kolor = wybrane_dane['icon'], wybrane_dane['color']

            # --- DYNAMICZNY CSS DLA ROZWIJANYCH RAMEK (EXPANDER) ---
            # Przeliczanie wybranego HEX na RGBA (półprzezroczyste tło wnętrza ramki)
            hex_c = kolor.lstrip('#')
            if len(hex_c) == 6:
                r, g, b = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
                bg_rgba = f"rgba({r}, {g}, {b}, 0.08)" # Lekko przezroczyste
            else:
                bg_rgba = "rgba(255, 255, 255, 0.05)"

            # Wstrzyknięcie stylów dopasowanych do wybranego planu
            st.markdown(f"""
            <style>
            div[data-testid="stExpander"] {{
                border: 2px solid {kolor} !important; 
                border-radius: 10px !important;
                background-color: {bg_rgba} !important; 
                overflow: hidden !important; 
            }}
            div[data-testid="stExpander"] summary {{
                background-color: {kolor} !important; 
            }}
            div[data-testid="stExpander"] summary p {{
                font-weight: 900 !important;
                font-size: 18px !important;
                color: #ffffff !important; 
                text-shadow: 1px 1px 3px rgba(0,0,0,0.5); /* Cień chroniący przed jasnymi kolorami */
            }}
            div[data-testid="stExpander"] summary svg {{
                color: #ffffff !important; 
            }}
            </style>
            """, unsafe_allow_html=True)

            st.markdown(f"<h3 style='color: {kolor}; margin-bottom: 0px;'>{ikona} Trening: {wybrany}</h3>",
                        unsafe_allow_html=True)
            st.markdown("---")

            plan_df = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=%s AND username=%s", conn,
                                        params=(wybrany, usr))
            if plan_df.empty:
                st.info("Ten plan jest pusty.")
            else:
                dt = st.date_input("Data", datetime.today())
                zrobione = []
                rc = st.session_state.reset_counter

                latest_weight = get_latest_weight(usr)
                if plan_df['masa_wlasna'].any() and latest_weight == 0.0:
                    st.warning(
                        "⚠️ Masz w planie ćwiczenia z masą własną, ale nie uzupełniłeś Pomiary (Waga). System policzy wagę ciała jako 0 kg.")

                # Przechodzimy przez każde ćwiczenie
                for i, r in plan_df.iterrows():
                    # --- ARCHITEKTURA MOBILNA ---
                    col_expander, col_done = st.columns([3, 1], vertical_alignment="center")

                    with col_expander:
                        with st.expander(f"🏋️ {r['cwiczenie']}"):
                            if r['na_czas'] == 1:
                                c_in1, c_in2 = st.columns(2)
                                s = c_in1.number_input("Serie", value=int(r['serie']), key=f"s_{r['id']}_{rc}")
                                cz = c_in2.number_input("Czas (s)", value=int(r['czas']), key=f"cz_{r['id']}_{rc}")
                                pompa = st.number_input("Pompa (1-5)", 1, 5, int(r['pompa_rate']), key=f"pr_{r['id']}_{rc}")
                                p, w, mw = 0, 0.0, 0
                            else:
                                c_in1, c_in2 = st.columns(2)
                                s = c_in1.number_input("Serie", value=int(r['serie']), key=f"s_{r['id']}_{rc}")
                                p = c_in2.number_input("Powt.", value=int(r['powtorzenia']), key=f"p_{r['id']}_{rc}")
                                
                                c_in3, c_in4 = st.columns(2, vertical_alignment="bottom")
                                mw = c_in3.toggle("Masa wł.", value=bool(r['masa_wlasna']), key=f"mw_{r['id']}_{rc}")
                                w = c_in4.number_input("+ Kg" if mw else "Kg", value=float(r['obciazenie']),
                                                       key=f"w_{r['id']}_{rc}")
                                
                                pompa = st.number_input("Pompa (1-5)", 1, 5, int(r['pompa_rate']), key=f"pr_{r['id']}_{rc}")
                                cz = 0

                    with col_done:
                        if st.toggle("Zrobione", key=f"z_{r['id']}_{rc}"):
                            zrobione.append({'c': r['cwiczenie'], 's': s, 'p': p, 'w': w, 'pr': pompa, 'mw': int(mw),
                                             'nc': int(r['na_czas']), 'cz': cz})
                    
                    st.markdown("<hr style='margin: 0.2em 0px; opacity: 0.2;'>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔥 ZAPISZ TRENING 🔥", type="primary", use_container_width=True):
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
                                (str(dt), wybrany, z['c'], z['s'], z['p'], z['w'], z['pr'], pts, z['mw'], z['nc'],
                                 z['cz'], usr))
                            c.execute(
                                "UPDATE plan SET serie=%s, powtorzenia=%s, obciazenie=%s, pompa_rate=%s, masa_wlasna=%s, na_czas=%s, czas=%s WHERE cwiczenie=%s AND kategoria=%s AND username=%s",
                                (z['s'], z['p'], z['w'], z['pr'], z['mw'], z['nc'], z['cz'], z['c'], wybrany, usr))
                        conn.commit()
                        st.session_state.reset_counter += 1
                        st.rerun()

    # 2. STATYSTYKI
    with all_tabs[1]:
        hist = pd.read_sql_query("SELECT * FROM historia WHERE username=%s ORDER BY data DESC", conn, params=(usr,))
        if not hist.empty:
            wykres_df = hist.groupby(['data', 'kategoria'])['punkty_pompy'].sum().reset_index()
            color_map = dict(zip(categories_df['name'], categories_df['color']))
            fig = px.bar(wykres_df, x='data', y='punkty_pompy', color='kategoria', color_discrete_map=color_map,
                         title="🔥 Suma punktów pompy w dniach")
            st.plotly_chart(fig, use_container_width=True)

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
                        if row['masa_wlasna'] == 1: return f"Masa wł. + {row['obciazenie']}kg" if row[
                                                                                                    'obciazenie'] > 0 else "Masa wł."
                        return f"{row['obciazenie']}kg"

                    display_df['Obciążenie/Czas'] = display_df.apply(format_obc, axis=1)
                    st.dataframe(display_df[['cwiczenie', 'serie', 'powtorzenia', 'Obciążenie/Czas']], hide_index=True,
                                 use_container_width=True)
                    for i, r in df_day.iterrows():
                        if st.button("Usuń", key=f"dh_{r['id']}"):
                            c = conn.cursor()
                            c.execute("DELETE FROM historia WHERE id=%s", (r['id'],))
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

    # 4. DYNAMICZNE ZAKŁADKI PLANÓW
    for i, row in categories_df.iterrows():
        with all_tabs[3 + i]: render_zarzadzanie_planem(row['name'], row['icon'], row['color'])

    # 5. USTAWIENIA PLANÓW
    with all_tabs[-1]:
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
            if st.form_submit_button("💾 ZAPISZ"):
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
            if c_2.button("Edytuj", key=f"ecat_{row['name']}"): st.session_state[edit_cat_key] = row['name']; st.rerun()
            if c_3.button("Usuń", key=f"del_cat_{row['name']}"):
                c = conn.cursor()
                c.execute("DELETE FROM categories WHERE name=%s AND username=%s", (row['name'], usr))
                conn.commit()
                st.rerun()


if __name__ == "__main__": main()
