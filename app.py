import streamlit as st
import pandas as pd
import sqlite3
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

DB_NAME = "baza_v3.db"


def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()


def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (
                     username
                     TEXT
                     PRIMARY
                     KEY,
                     password
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY,
                     name
                     TEXT,
                     username
                     TEXT,
                     icon
                     TEXT,
                     color
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS plan
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY,
                     kategoria
                     TEXT,
                     cwiczenie
                     TEXT,
                     opis
                     TEXT,
                     serie
                     INTEGER,
                     powtorzenia
                     INTEGER,
                     obciazenie
                     REAL,
                     pompa_rate
                     INTEGER,
                     username
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS historia
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY,
                     data
                     TEXT,
                     kategoria
                     TEXT,
                     cwiczenie
                     TEXT,
                     serie
                     INTEGER,
                     powtorzenia
                     INTEGER,
                     obciazenie
                     REAL,
                     pompa_rate
                     INTEGER,
                     punkty_pompy
                     REAL,
                     username
                     TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pomiary
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY,
                     data
                     TEXT,
                     waga
                     REAL,
                     username
                     TEXT
                 )''')

    try:
        c.execute("ALTER TABLE categories ADD COLUMN icon TEXT DEFAULT '💪'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE categories ADD COLUMN color TEXT DEFAULT '#FFD700'")
    except sqlite3.OperationalError:
        pass

    c.execute("SELECT COUNT(*) FROM categories WHERE username = 'Główny'")
    if c.fetchone()[0] == 0:
        default_cats = [("Push", "✋", "#FF4B4B"), ("Pull", "✊", "#00CCFF"), ("Nogi", "🦵", "#00FF00")]
        for nazwa, ikona, kolor in default_cats:
            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (?, 'Główny', ?, ?)",
                      (nazwa, ikona, kolor))

    conn.commit()
    conn.close()


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
                conn = sqlite3.connect(DB_NAME);
                c = conn.cursor()
                c.execute("SELECT password FROM users WHERE username = ?", (u,))
                data = c.fetchone()
                if data and check_hashes(p, data[0]):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("Błędny login lub hasło")
                conn.close()
        with tab_reg:
            nu = st.text_input("Nowy Login", key="reg_u")
            np = st.text_input("Nowe Hasło", type="password", key="reg_p")
            if st.button("Zarejestruj", use_container_width=True):
                if nu and np:
                    conn = sqlite3.connect(DB_NAME);
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username = ?", (nu,))
                    if c.fetchone():
                        st.error("Login zajęty!")
                    else:
                        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (nu, make_hashes(np)))
                        default_cats = [("Push", "✋", "#FF4B4B"), ("Pull", "✊", "#00CCFF"), ("Nogi", "🦵", "#00FF00")]
                        for nazwa, ikona, kolor in default_cats:
                            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (?, ?, ?, ?)",
                                      (nazwa, nu, ikona, kolor))
                        conn.commit();
                        st.success("Konto gotowe! Zaloguj się.")
                    conn.close()
    return False


def render_zarzadzanie_planem(kategoria_nazwa, ikona, kolor):
    usr = st.session_state.username
    conn = sqlite3.connect(DB_NAME)
    df_plan = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=? AND username=?", conn,
                                params=(kategoria_nazwa, usr))

    edit_key = f"edit_id_{kategoria_nazwa}_{usr}"
    if edit_key not in st.session_state: st.session_state[edit_key] = None

    st.markdown(f"<h3 style='color: {kolor};'>{ikona} Plan: {kategoria_nazwa}</h3>", unsafe_allow_html=True)

    if not df_plan.empty:
        for idx, row in df_plan.iterrows():
            c_a, c_b, c_c = st.columns([5, 0.8, 0.8], vertical_alignment="center")
            c_a.write(f"**{row['cwiczenie']}** | {row['serie']}x{row['powtorzenia']} | {row['obciazenie']}kg")
            with c_b:
                if st.button("Edytuj", key=f"ed_{row['id']}"):
                    st.session_state[edit_key] = row['id'];
                    st.rerun()
            with c_c:
                if st.button("Usuń", key=f"del_{row['id']}"):
                    c = conn.cursor();
                    c.execute("DELETE FROM plan WHERE id=?", (row['id'],));
                    conn.commit();
                    st.rerun()
    else:
        st.info("Dodaj pierwsze ćwiczenie do tego planu.")

    st.markdown("---")
    edit_id = st.session_state[edit_key]
    d_n, d_s, d_p, d_o, d_pr = ("", 3, 10, 0.0, 3)
    if edit_id:
        c = conn.cursor();
        c.execute("SELECT cwiczenie, serie, powtorzenia, obciazenie, pompa_rate FROM plan WHERE id=?", (edit_id,))
        res = c.fetchone()
        if res: d_n, d_s, d_p, d_o, d_pr = res

    with st.form(f"form_{kategoria_nazwa}", clear_on_submit=True):
        st.markdown(f"**{'Edytuj' if edit_id else 'Dodaj nowe'} ćwiczenie**")
        c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1])
        nazwa = c1.text_input("Nazwa", value=d_n)
        serie = c2.number_input("Serie", min_value=1, value=int(d_s))
        powt = c3.number_input("Powtórzenia", min_value=1, value=int(d_p))
        obc = c4.number_input("Obciążenie", min_value=0.0, format="%g", value=float(d_o))
        pompa = st.slider("POMPA", 1, 5, int(d_pr))
        if st.form_submit_button("ZAPISZ"):
            if nazwa:
                c = conn.cursor()
                if edit_id:
                    c.execute(
                        "UPDATE plan SET cwiczenie=?, serie=?, powtorzenia=?, obciazenie=?, pompa_rate=? WHERE id=?",
                        (nazwa, serie, powt, obc, pompa, edit_id))
                    st.session_state[edit_key] = None
                else:
                    c.execute(
                        "INSERT INTO plan (kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, username) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (kategoria_nazwa, nazwa, serie, powt, obc, pompa, usr))
                conn.commit();
                st.rerun()
    if edit_id:
        if st.button("Anuluj edycję"): st.session_state[edit_key] = None; st.rerun()
    conn.close()


def main():
    init_db()
    if not auth_screen(): return
    usr = st.session_state.username
    if 'reset_counter' not in st.session_state: st.session_state.reset_counter = 0

    st.markdown(
        "<h1 style='text-align: center; color: #FFD700; font-size: 3rem; font-weight: 900; text-transform: uppercase;'>💪 PIZDA OGIEŃ !!!</h1>",
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    conn = sqlite3.connect(DB_NAME)
    categories_df = pd.read_sql_query("SELECT name, icon, color FROM categories WHERE username = ?", conn,
                                      params=(usr,))
    conn.close()

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

            st.markdown(f"<h3 style='color: {kolor}; margin-bottom: 0px;'>{ikona} Trening: {wybrany}</h3>",
                        unsafe_allow_html=True)
            st.markdown("---")

            conn = sqlite3.connect(DB_NAME);
            plan_df = pd.read_sql_query("SELECT * FROM plan WHERE kategoria=? AND username=?", conn,
                                        params=(wybrany, usr));
            conn.close()
            if plan_df.empty:
                st.info("Ten plan jest pusty.")
            else:
                dt = st.date_input("Data", datetime.today());
                zrobione = [];
                rc = st.session_state.reset_counter

                bg_color = kolor + "33" if len(kolor) == 7 else kolor

                for i, r in plan_df.iterrows():
                    # Zmienione proporcje kolumn, żeby "Powtórzenia" i "Obciążenie" ładnie się mieściły
                    c1, c2, c3, c4, c5, c6 = st.columns([2.5, 0.9, 1.2, 1.2, 1.2, 1.5], vertical_alignment="center")

                    styled_name = f"""
                    <div style='
                        background-color: {bg_color}; 
                        border-left: 5px solid {kolor}; 
                        padding: 10px 15px; 
                        border-radius: 6px; 
                        font-weight: 800;
                        font-size: 16px;
                    '>
                        {r['cwiczenie']}
                    </div>
                    """
                    c1.markdown(styled_name, unsafe_allow_html=True)

                    # NOWE ETYKIETY: Serie, Powtórzenia, Obciążenie
                    s = c2.number_input("Serie", value=int(r['serie']), key=f"s_{r['id']}_{rc}")
                    p = c3.number_input("Powtórzenia", value=int(r['powtorzenia']), key=f"p_{r['id']}_{rc}")
                    w = c4.number_input("Obciążenie", value=float(r['obciazenie']), key=f"w_{r['id']}_{rc}")
                    pompa = c5.number_input("Pompa", 1, 5, int(r['pompa_rate']), key=f"pr_{r['id']}_{rc}")

                    if c6.toggle("Zrobione", key=f"z_{r['id']}_{rc}"):
                        zrobione.append({'c': r['cwiczenie'], 's': s, 'p': p, 'w': w, 'pr': pompa})

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔥 ZAPISZ TRENING 🔥", type="primary", use_container_width=True):
                    if zrobione:
                        conn = sqlite3.connect(DB_NAME);
                        c = conn.cursor()
                        for z in zrobione:
                            w_c = z['w'] if z['w'] > 0 else 1
                            pts = z['s'] * z['p'] * w_c * z['pr']
                            c.execute(
                                "INSERT INTO historia (data, kategoria, cwiczenie, serie, powtorzenia, obciazenie, pompa_rate, punkty_pompy, username) VALUES (?,?,?,?,?,?,?,?,?)",
                                (str(dt), wybrany, z['c'], z['s'], z['p'], z['w'], z['pr'], pts, usr))
                            c.execute(
                                "UPDATE plan SET serie=?, powtorzenia=?, obciazenie=?, pompa_rate=? WHERE cwiczenie=? AND kategoria=? AND username=?",
                                (z['s'], z['p'], z['w'], z['pr'], z['c'], wybrany, usr))
                        conn.commit();
                        conn.close();
                        st.session_state.reset_counter += 1;
                        st.rerun()

    # 2. STATYSTYKI Z ROZWIJANĄ HISTORIĄ
    with all_tabs[1]:
        conn = sqlite3.connect(DB_NAME)
        hist = pd.read_sql_query("SELECT * FROM historia WHERE username=? ORDER BY data DESC", conn, params=(usr,))
        conn.close()

        if not hist.empty:
            wykres_df = hist.groupby('data')['punkty_pompy'].sum().reset_index()
            st.plotly_chart(px.bar(wykres_df, x='data', y='punkty_pompy', color_discrete_sequence=['#FFD700']),
                            use_container_width=True)

            st.markdown("### 📅 Historia Twoich Treningów")
            st.markdown("Kliknij w datę, aby rozwinąć szczegóły wpisu.")

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
                    display_df = df_day[['cwiczenie', 'serie', 'powtorzenia', 'obciazenie']].copy()
                    display_df.columns = ['Ćwiczenie', 'Serie', 'Powtórzenia', 'Obciążenie (kg)']
                    st.dataframe(display_df, hide_index=True, use_container_width=True)

                    st.markdown("<br><small style='color: gray;'>Zarządzanie wpisami (usuwanie pomyłek):</small>",
                                unsafe_allow_html=True)
                    for i, r in df_day.iterrows():
                        c1, c2 = st.columns([4, 1])
                        c1.write(f"🗑️ {r['cwiczenie']} ({r['serie']}x{r['powtorzenia']} | {r['obciazenie']}kg)")
                        if c2.button("Usuń", key=f"dh_{r['id']}"):
                            conn = sqlite3.connect(DB_NAME);
                            c = conn.cursor()
                            c.execute("DELETE FROM historia WHERE id=?", (r['id'],))
                            conn.commit();
                            conn.close();
                            st.rerun()
        else:
            st.info("Brak historii treningów. Zrób pierwszy trening!")

    # 3. POMIARY
    with all_tabs[2]:
        with st.form("pomiar"):
            c1, c2 = st.columns(2);
            d_p = c1.date_input("Data");
            w_p = c2.number_input("Waga (kg)", 30.0, 200.0, 80.0, 0.1)
            if st.form_submit_button("DODAJ"):
                conn = sqlite3.connect(DB_NAME);
                c = conn.cursor();
                c.execute("INSERT INTO pomiary (data, waga, username) VALUES (?,?,?)", (str(d_p), w_p, usr));
                conn.commit();
                st.rerun()
        conn = sqlite3.connect(DB_NAME);
        p_df = pd.read_sql_query("SELECT * FROM pomiary WHERE username=? ORDER BY data ASC", conn, params=(usr,));
        conn.close()
        if not p_df.empty: st.plotly_chart(
            px.line(p_df, x='data', y='waga', markers=True, color_discrete_sequence=['#FFD700']),
            use_container_width=True)

    # 4. DYNAMICZNE ZAKŁADKI PLANÓW
    for i, row in categories_df.iterrows():
        with all_tabs[3 + i]:
            render_zarzadzanie_planem(row['name'], row['icon'], row['color'])

    # 5. USTAWIENIA PLANÓW (EDYCJA I ZARZĄDZANIE)
    with all_tabs[-1]:
        edit_cat_key = f"edit_cat_{usr}"
        if edit_cat_key not in st.session_state: st.session_state[edit_cat_key] = None
        edit_cat_name = st.session_state[edit_cat_key]

        d_cat_name = ""
        d_cat_icon = "🏋️"
        d_cat_color = "#FFD700"

        if edit_cat_name:
            cat_data = categories_df[categories_df['name'] == edit_cat_name].iloc[0]
            d_cat_name = cat_data['name']
            d_cat_icon = cat_data['icon']
            d_cat_color = cat_data['color']

        st.subheader("⚙️ " + ("Edytuj plan" if edit_cat_name else "Dodaj nowy plan do swojego zestawu"))

        with st.form("cat_form", clear_on_submit=True):
            col_1, col_2, col_3 = st.columns([3, 1, 1])
            new_cat_name = col_1.text_input("Nazwa planu (np. Cardio)", value=d_cat_name)

            ikony_do_wyboru = ["🏋️", "🏃", "🤸", "💪", "🦵", "✋", "✊", "🧘", "🚲", "🏊", "🔥", "🦍", "🦖", "🏆"]
            icon_idx = ikony_do_wyboru.index(d_cat_icon) if d_cat_icon in ikony_do_wyboru else 0
            new_cat_icon = col_2.selectbox("Ikona", ikony_do_wyboru, index=icon_idx)
            new_cat_color = col_3.color_picker("Wybierz kolor przewodni", d_cat_color)

            submit_btn = st.form_submit_button("💾 ZAPISZ ZMIANY" if edit_cat_name else "DODAJ PLAN")

            if submit_btn:
                if new_cat_name:
                    conn = sqlite3.connect(DB_NAME);
                    c = conn.cursor()
                    if edit_cat_name:
                        if new_cat_name != edit_cat_name:
                            c.execute("SELECT * FROM categories WHERE name=? AND username=?", (new_cat_name, usr))
                            if c.fetchone():
                                st.error("Masz już inny plan o takiej nazwie!")
                                conn.close()
                                st.stop()

                        c.execute("UPDATE categories SET name=?, icon=?, color=? WHERE name=? AND username=?",
                                  (new_cat_name, new_cat_icon, new_cat_color, edit_cat_name, usr))
                        c.execute("UPDATE plan SET kategoria=? WHERE kategoria=? AND username=?",
                                  (new_cat_name, edit_cat_name, usr))
                        c.execute("UPDATE historia SET kategoria=? WHERE kategoria=? AND username=?",
                                  (new_cat_name, edit_cat_name, usr))
                        conn.commit()
                        st.session_state[edit_cat_key] = None
                        st.success("Plan zaktualizowany!")
                    else:
                        c.execute("SELECT * FROM categories WHERE name=? AND username=?", (new_cat_name, usr))
                        if c.fetchone():
                            st.error("Masz już plan o takiej nazwie!")
                        else:
                            c.execute("INSERT INTO categories (name, username, icon, color) VALUES (?, ?, ?, ?)",
                                      (new_cat_name, usr, new_cat_icon, new_cat_color))
                            conn.commit();
                            st.success("Dodano!")
                    conn.close();
                    st.rerun()

        if edit_cat_name:
            if st.button("❌ Anuluj edycję planu"):
                st.session_state[edit_cat_key] = None;
                st.rerun()

        st.divider()
        st.write("Twoje plany (możesz usunąć puste lub je edytować):")
        for idx, row in categories_df.iterrows():
            c_1, c_2, c_3 = st.columns([3, 0.8, 0.8], vertical_alignment="center")
            c_1.markdown(
                f"<span style='color:{row['color']}; font-weight:bold; font-size: 18px;'>{row['icon']} {row['name']}</span>",
                unsafe_allow_html=True)

            with c_2:
                if st.button("Edytuj", key=f"ecat_{row['name']}"):
                    st.session_state[edit_cat_key] = row['name'];
                    st.rerun()
            with c_3:
                if st.button("Usuń", key=f"del_cat_{row['name']}"):
                    conn = sqlite3.connect(DB_NAME);
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM plan WHERE kategoria=? AND username=?", (row['name'], usr))
                    if c.fetchone()[0] > 0:
                        st.error("Nie można usunąć planu, który zawiera ćwiczenia!")
                    else:
                        c.execute("DELETE FROM categories WHERE name=? AND username=?", (row['name'], usr))
                        conn.commit();
                        st.rerun()
                    conn.close()


if __name__ == "__main__": main()