import streamlit as st
import pandas as pd
import re
import requests
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# --- SIVUN KONFIGURAATIO ---
st.set_page_config(page_title="Ässät Koppi-Apuri", page_icon="🏒", layout="centered")

# --- TYYLITYS ---
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: white; }
    .stButton>button { 
        width: 100%; border-radius: 5px; height: 3em; 
        background-color: #CC0000 !important; color: white !important; font-weight: bold;
    }
    label, p, span { color: white !important; }
    .stDateInput div, .stTextInput div { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

# --- JOUKKUEET ---
JOUKKUEET = [
    {"nimi": "Ässät U12", "ical": "https://ics.jopox.fi/hockeypox/calendar/ical.php?ics=true&e=t&cal=U122014_9664", "club_id": "9664"},
    {"nimi": "Ässät U13", "ical": "https://ics.jopox.fi/hockeypox/calendar/ical.php?ics=true&e=t&cal=U132013_9665", "club_id": "9665"},
    {"nimi": "Ässät U14", "ical": "https://ics.jopox.fi/hockeypox/calendar/ical.php?ics=true&e=t&cal=U142012_9666", "club_id": "9666"},
    {"nimi": "Ässät Maalivahdit", "ical": "https://ics.jopox.fi/hockeypox/calendar/ical.php?ics=true&e=t&cal=Maalivahtijaatoiminta_9681", "club_id": "9681"}
]

# --- KÄYTTÖLIITTYMÄ ---
st.title("🏒 ÄSSÄT KOPPI-APURI v1.0 (Web)")

with st.form("haku_lomake"):
    col1, col2 = st.columns(2)
    with col1:
        user = st.text_input("Jopox Tunnus (Sähköposti)")
        alku_pvm = st.date_input("Alku päivä", datetime.now())
    with col2:
        pw = st.text_input("Salasana", type="password")
        loppu_pvm = st.date_input("Loppu päivä", datetime.now() + timedelta(days=7))
    
    halli_valinta = st.selectbox("Valitse Halli", ["0 (Kaikki)", "1 (Astora)", "2 (Isomäki)"])
    aja_haku = st.form_submit_button("KÄYNNISTÄ HAKU")

if aja_haku:
    if not user or not pw:
        st.error("Syötä Jopox-tunnukset!")
    else:
        tulokset = []
        with st.status("Haetaan tietoja...", expanded=True) as status:
            try:
                os.system("playwright install firefox")
                
                with sync_playwright() as p:
                    browser = p.firefox.launch(headless=True)
                    context = browser.new_context(viewport={'width': 1280, 'height': 800})
                    page = context.new_page()

                    # 1. VARMA KIRJAUTUMINEN
                    st.write("Kirjaudutaan Jopoxiin...")
                    page.goto("https://login.jopox.fi/login?to=145")
                    
                    # Odotetaan mitä tahansa tekstikenttää
                    page.wait_for_selector("input", timeout=30000)
                    
                    # Syötetään tunnukset suoraan kohdistamalla ensimmäiseen kenttään
                    page.focus("input")
                    page.keyboard.type(user)
                    page.keyboard.press("Tab")
                    page.keyboard.type(pw)
                    page.keyboard.press("Enter")
                    
                    page.wait_for_timeout(5000) # Annetaan sivun rauhassa vaihtua

                    # 2. PAKOTETTU SELAINVERSIO
                    try:
                        # Etsitään linkkiä, joka sisältää tekstin "selainversio"
                        btn = page.locator("a:has-text('selainversio'), a:has-text('browser version')").first
                        if btn.is_visible():
                            st.write("Siirrytään selainversioon...")
                            btn.click()
                            page.wait_for_timeout(3000)
                    except:
                        pass

                    # 3. HAKU-SILMUKKA
                    curr = datetime.combine(alku_pvm, datetime.min.time())
                    loppu = datetime.combine(loppu_pvm, datetime.min.time())

                    while curr <= loppu:
                        etsi_pvm = curr.strftime('%Y%m%d')
                        nayta_pvm = curr.strftime('%d.%m.%Y')
                        st.write(f"Käsitellään: {nayta_pvm}...")

                        for j in JOUKKUEET:
                            try:
                                res = requests.get(j['ical'], timeout=10)
                                ical = res.text.replace("\r\n ", "").replace("\n ", "")
                                
                                for seg in ical.split("BEGIN:VEVENT"):
                                    if etsi_pvm in seg and "END:VEVENT" in seg:
                                        # Sijaintisuodatus
                                        loc = re.search(r"LOCATION:(.*)", seg)
                                        paikka = loc.group(1).strip().replace("\\,", ",") if loc else "Pori"
                                        h_id = halli_valinta[0]
                                        if h_id == "1" and "astora" not in paikka.lower(): continue
                                        if h_id == "2" and ("isomäki" not in paikka.lower() and "harjoitushalli" not in paikka.lower()): continue

                                        # Kellonaika
                                        a_m = re.search(r"DTSTART.*T(\d{2})(\d{2})", seg)
                                        e_m = re.search(r"DTEND.*T(\d{2})(\d{2})", seg)
                                        klo = f"{a_m.group(1)}:{a_m.group(2)} - {e_m.group(1)}:{e_m.group(2)}" if a_m and e_m else "--:--"

                                        uid = re.search(r"UID:(.*)", seg)
                                        if uid:
                                            uid_nro = "".join(filter(str.isdigit, uid.group(1)))
                                            t_path = "game" if "game" in uid.group(1).lower() else "training"
                                            
                                            page.goto(f"https://assat-app.jopox.fi/{t_path}/club/{j['club_id']}/{uid_nro}")
                                            
                                            try:
                                                # Odotetaan .chip-elementtejä (pelaajakortit)
                                                page.wait_for_selector(".chip", timeout=20000)
                                                maara = page.locator(".chip").count()
                                                
                                                tulokset.append({
                                                    "Pvm": nayta_pvm, "Klo": klo, "Tyyppi": "PELI" if t_path == "game" else "HKT",
                                                    "Joukkue": j['nimi'], "Paikka": paikka, "Hlö": maara,
                                                    "Tarve": "2 KOPPIA" if maara > 16 else "1 KOPPI"
                                                })
                                            except:
                                                st.warning(f"Ei ilmoittautuneita: {nayta_pvm} {klo}")
                            except:
                                continue
                        curr += timedelta(days=1)

                    browser.close()
                
                status.update(label="Haku valmis!", state="complete", expanded=False)

                if tulokset:
                    df = pd.DataFrame(tulokset)
                    st.table(df)
                    st.divider()
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 LATAA CSV", csv, f"kopit_{datetime.now().strftime('%d%m%Y')}.csv", "text/csv")
                else:
                    st.warning("Tapahtumia ei löytynyt.")

            except Exception as e:
                st.error(f"Kriittinen virhe: {e}")