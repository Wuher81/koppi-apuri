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
        width: 100%; 
        border-radius: 5px; 
        height: 3em; 
        background-color: #CC0000 !important; 
        color: white !important; 
        font-weight: bold;
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
        user = st.text_input("Jopox Tunnus")
        alku_pvm = st.date_input("Alku päivä", datetime.now())
    with col2:
        pw = st.text_input("Salasana", type="password")
        loppu_pvm = st.date_input("Loppu päivä", datetime.now() + timedelta(days=7))
    
    halli_valinta = st.selectbox("Valitse Halli", ["0 (Kaikki)", "1 (Astora)", "2 (Isomäki)"])
    aja_haku = st.form_submit_button("KÄYNNISTÄ HAKU")

# --- HAKULOGIIKKA ---
if aja_haku:
    if not user or not pw:
        st.error("Syötä Jopox-tunnukset!")
    else:
        tulokset = []
        with st.status("Valmistellaan selainta...", expanded=True) as status:
            try:
                # Varmistetaan selain pilvessä
                os.system("playwright install firefox")
                
                with sync_playwright() as p:
                    browser = p.firefox.launch(headless=True)
                    context = browser.new_context(viewport={'width': 1280, 'height': 800})
                    page = context.new_page()

                    # Kirjautuminen
                    st.write("Kirjaudutaan Jopoxiin...")
                    page.goto("https://login.jopox.fi/login?to=145")
                    target = page
                    for f in page.frames:
                        if f.locator("input[type='password']").count() > 0:
                            target = f; break
                    
                    target.locator("input[type='password']").fill(user)
                    page.keyboard.press("Tab")
                    page.keyboard.type(pw)
                    page.keyboard.press("Enter")
                    
                    # Siirtyminen selainversioon
                    try:
                        btn = page.locator("text=/TO BROWSER VERSION|SIIRRY SELAINVERSIOON/i")
                        btn.wait_for(state="visible", timeout=7000)
                        btn.click()
                    except:
                        pass 

                    curr = datetime.combine(alku_pvm, datetime.min.time())
                    loppu = datetime.combine(loppu_pvm, datetime.min.time())

                    while curr <= loppu:
                        etsi_pvm = curr.strftime('%Y%m%d')
                        nayta_pvm = curr.strftime('%d.%m.%Y')
                        st.write(f"Käsitellään: {nayta_pvm}...")

                        for j in JOUKKUEET:
                            res = requests.get(j['ical'], headers={'Cache-Control': 'no-cache'})
                            ical = res.text.replace("\r\n ", "").replace("\n ", "")
                            
                            for seg in ical.split("BEGIN:VEVENT"):
                                if etsi_pvm in seg and "END:VEVENT" in seg:
                                    loc = re.search(r"LOCATION:(.*)", seg)
                                    paikka = loc.group(1).strip().replace("\\,", ",") if loc else "Pori"
                                    h_id = halli_valinta[0]
                                    if h_id == "1" and "astora" not in paikka.lower(): continue
                                    if h_id == "2" and ("isomäki" not in paikka.lower() and "harjoitushalli" not in paikka.lower()): continue

                                    a_m = re.search(r"DTSTART.*T(\d{2})(\d{2})", seg)
                                    e_m = re.search(r"DTEND.*T(\d{2})(\d{2})", seg)
                                    klo = f"{a_m.group(1)}:{a_m.group(2)} - {e_m.group(1)}:{e_m.group(2)}" if a_m and e_m else "--:--"

                                    uid = re.search(r"UID:(.*)", seg)
                                    if uid:
                                        uid_nro = "".join(filter(str.isdigit, uid.group(1)))
                                        t_path = "game" if "game" in uid.group(1).lower() else "training"
                                        page.goto(f"https://assat-app.jopox.fi/{t_path}/club/{j['club_id']}/{uid_nro}", wait_until="networkidle")
                                        
                                        try:
                                            # Odotetaan että sivu latautuu kunnolla
                                            page.wait_for_selector("#yesBox", timeout=15000)
                                            
                                            # Lasketaan kaikki mahdolliset pelaajaelementit laatikon sisältä
                                            # Tämä laskee .chip, .player-card ja muut yleiset elementit
                                            pelaajat = page.locator("#yesBox .chip, #yesBox .player, #yesBox [class*='player']").count()
                                            
                                            # Jos laskuri näyttää nollaa, kokeillaan vielä yleisempää hakua
                                            if pelaajat == 0:
                                                pelaajat = page.locator("#yesBox > div > div").count()

                                            tulokset.append({
                                                "Pvm": nayta_pvm, 
                                                "Klo": klo, 
                                                "Tyyppi": "PELI" if t_path == "game" else "HKT",
                                                "Joukkue": j['nimi'], 
                                                "Paikka": paikka, 
                                                "Hlö": pelaajat,
                                                "Tarve": "2 KOPPIA" if pelaajat > 16 else "1 KOPPI"
                                            })
                                        except:
                                            # Jos sivu ei lataudu, kokeillaan kerran uudestaan
                                            st.warning(f"Ei saatu tietoja: {nayta_pvm} {klo} (Timeout)")

                        # TÄRKEÄÄ: curr on tässä sisennyksessä, for-joukkueiden ulkopuolella
                        curr += timedelta(days=1)

                    browser.close() # Suljetaan selain haku-loopin jälkeen
                
                status.update(label="Haku valmis!", state="complete", expanded=False)

                if tulokset:
                    df = pd.DataFrame(tulokset)
                    st.dataframe(df.style.applymap(lambda x: 'color: #CC0000; font-weight: bold' if x == '2 KOPPIA' else '', subset=['Tarve']), use_container_width=True)
                    st.divider()
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 LATAA CSV", csv, f"kopit_{datetime.now().strftime('%d%m%Y')}.csv", "text/csv")
                else:
                    st.warning("Ei tapahtumia.")

            except Exception as e:
                st.error(f"Virhe: {e}")