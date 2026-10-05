import sys
import asyncio
import streamlit as st
import datetime
from skyfield.api import load, wgs84
from skyfield import almanac
from hijri_converter import Hijri

# -------------------------------------------------------------
# PATCH WINDOWS ASYNCIO EVENT LOOP (Mencegah error di sistem Windows)
# -------------------------------------------------------------
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

st.set_page_config(page_title="Evaluasi Hilal MABIMS - Aceh", layout="wide")

st.title("🌙 Evaluasi Hilal MABIMS Otomatis (Engine Skyfield)")
st.caption("Lokasi Pengamatan: Banda Aceh (5.5483° N, 95.3238° E)")

# Load Data Ephemeris NASA (DE421)
@st.cache_resource
def load_ephemeris():
    ts = load.timescale()
    eph = load('de421.bsp')
    return ts, eph

ts, eph = load_ephemeris()
earth, sun, moon = eph['earth'], eph['sun'], eph['moon']

# DEFINISI KOORDINAT BANDA ACEH (Dengan Ketinggian Topografi)
aceh_geo = wgs84.latlon(latitude_degrees=5.5483, longitude_degrees=95.3238, elevation_m=7.0)
aceh_location = earth + aceh_geo

# -------------------------------------------------------------
# DAFTAR BULAN HIJRIAH
# -------------------------------------------------------------
BULAN_HIJRIAH = [
    "1. Muharram", "2. Safar", "3. Rabi'ul Awal", "4. Rabi'ul Akhir",
    "5. Jumadil Awal", "6. Jumadil Akhir", "7. Rajab", "8. Sya'ban",
    "9. Ramadhan", "10. Syawwal", "11. Zulqa'dah", "12. Zulhijjah"
]

st.sidebar.header("🗓️ Input Tahun & Bulan Hijriah")
tahun_hijriah = st.sidebar.number_input("Tahun Hijriah (H):", min_value=1445, max_value=1460, value=1447)
bulan_hijriah_pilihan = st.sidebar.selectbox("Pilih Awal Bulan Hijriah:", BULAN_HIJRIAH, index=8) # Default: Ramadhan

idx_bulan_hijriah = BULAN_HIJRIAH.index(bulan_hijriah_pilihan) + 1

if st.sidebar.button("Hitung Hilal Otomatis"):
    with st.spinner(f"Menghitung Ijtima' dan Posisi Hilal Awal {bulan_hijriah_pilihan.split('. ')[1]} {tahun_hijriah} H..."):
        # -------------------------------------------------------------
        # KONVERSI HIJRIAH KE MASEHI UNTUK MENENTUKAN RENTANG PENCARIAN
        # -------------------------------------------------------------
        # Menggunakan tanggal 15 bulan sebelumnya agar aman dari batas umur bulan (29/30 hari)
        bulan_prev_h = 12 if idx_bulan_hijriah == 1 else idx_bulan_hijriah - 1
        tahun_prev_h = tahun_hijriah - 1 if idx_bulan_hijriah == 1 else tahun_hijriah
        
        # Konversi tgl 15 bulan sebelum Hijriah ke Masehi sebagai awal rentang
        greg_approx = Hijri(tahun_prev_h, bulan_prev_h, 15).to_gregorian()
        
        t0 = ts.utc(greg_approx.year, greg_approx.month, greg_approx.day)
        # Rentang pencarian ijtima' selama 30 hari ke depan
        dt_t1 = datetime.datetime(greg_approx.year, greg_approx.month, greg_approx.day) + datetime.timedelta(days=30)
        t1 = ts.utc(dt_t1.year, dt_t1.month, dt_t1.day)

        t_events, y_events = almanac.find_discrete(t0, t1, almanac.moon_phases(eph))
        
        t_ijtima = None
        for t_evt, y_evt in zip(t_events, y_events):
            if y_evt == 0:  # New Moon / Ijtima'
                t_ijtima = t_evt
                break

        if t_ijtima is None:
            st.error("Ijtima' tidak ditemukan pada rentang bulan ini.")
        else:
            # Waktu Ijtima' dalam WIB (UTC+7)
            dt_ijtima_utc = t_ijtima.utc_datetime()
            dt_ijtima_wib = dt_ijtima_utc + datetime.timedelta(hours=7)

            # Hitung Sunset perkiraan pada hari terjadinya ijtima'
            t_start_ij = ts.utc(dt_ijtima_utc.year, dt_ijtima_utc.month, dt_ijtima_utc.day, 0, 0)
            t_end_ij = ts.utc(dt_ijtima_utc.year, dt_ijtima_utc.month, dt_ijtima_utc.day, 23, 59)
            
            f_ij = almanac.sunrise_sunset(eph, aceh_geo)
            t_s_events, y_s_events = almanac.find_discrete(t_start_ij, t_end_ij, f_ij)
            
            t_sunset_hari_ij = None
            for t_s, y_s in zip(t_s_events, y_s_events):
                if y_s == 0:  # Sunset
                    t_sunset_hari_ij = t_s
                    break
            
            if t_sunset_hari_ij is not None:
                dt_sunset_ij_wib = t_sunset_hari_ij.utc_datetime() + datetime.timedelta(hours=7)
            else:
                dt_sunset_ij_wib = dt_ijtima_wib

            # LOGIKA KETENTUAN KHUSUS:
            if (dt_ijtima_wib.time() > dt_sunset_ij_wib.time()) and (dt_ijtima_wib.date() == dt_sunset_ij_wib.date()):
                dt_rukyat_date = dt_ijtima_wib.date() + datetime.timedelta(days=1)
                catatan_rukyat = f"⚠ Ijtima' penentuan awal {bulan_hijriah_pilihan.split('. ')[1]} {tahun_hijriah} H terjadi setelah sunset. Observasi rukyat dilakukan keesokan harinya."
            else:
                dt_rukyat_date = dt_ijtima_wib.date()
                catatan_rukyat = f"ℹ️ Ijtima' penentuan awal {bulan_hijriah_pilihan.split('. ')[1]} {tahun_hijriah} H terjadi sebelum sunset. Observasi rukyat dilakukan pada hari ijtima' tersebut."

            # -------------------------------------------------------------
            # LANGKAH 2: Cari Waktu Sunset pada HARI RUKYAT
            # -------------------------------------------------------------
            t_start_rukyat = ts.utc(dt_rukyat_date.year, dt_rukyat_date.month, dt_rukyat_date.day, 0, 0)
            t_end_rukyat = ts.utc(dt_rukyat_date.year, dt_rukyat_date.month, dt_rukyat_date.day, 23, 59)

            f_rukyat = almanac.sunrise_sunset(eph, aceh_geo)
            t_s_rukyat_events, y_s_rukyat_events = almanac.find_discrete(t_start_rukyat, t_end_rukyat, f_rukyat)

            t_sunset = None
            for t_s, y_s in zip(t_s_rukyat_events, y_s_rukyat_events):
                if y_s == 0:  # Sunset
                    t_sunset = t_s
                    break

            if t_sunset is None:
                t_sunset = ts.utc(dt_rukyat_date.year, dt_rukyat_date.month, dt_rukyat_date.day, 11, 45)

            dt_sunset_wib = t_sunset.utc_datetime() + datetime.timedelta(hours=7)

            # -------------------------------------------------------------
            # LANGKAH 3: Ambil Tinggi Hilal & Elongasi pada Saat Sunset
            # -------------------------------------------------------------
            ast_moon = aceh_location.at(t_sunset).observe(moon).apparent()
            ast_sun = aceh_location.at(t_sunset).observe(sun).apparent()

            # Refraksi atmosfer standar (15°C, 1010 mbar)
            alt_moon, az_moon, _ = ast_moon.altaz(temperature_C=15.0, pressure_mbar=1010.0)
            tinggi_hilal = alt_moon.degrees
            elongasi = ast_moon.separation_from(ast_sun).degrees

            # Evaluasi Kriteria MABIMS
            is_mabims = (tinggi_hilal >= 3.0) and (elongasi >= 6.4)

            # Output UI Streamlit
            st.markdown("---")
            st.info(catatan_rukyat)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📌 Waktu Ijtima' (WIB)", dt_ijtima_wib.strftime("%Y-%m-%d %H:%M:%S"))
            col2.metric("🌅 Sunset Rukyat Aceh", dt_sunset_wib.strftime("%Y-%m-%d %H:%M:%S"))
            col3.metric("📐 Tinggi Hilal", f"{tinggi_hilal:.2f}°")
            col4.metric("↔️ Elongasi", f"{elongasi:.2f}°")

            nama_bulan_saja = bulan_hijriah_pilihan.split('. ')[1]

            if is_mabims:
                st.success(f"✅ **STATUS: MEMENUHI KRITERIA MABIMS (Imkanur Rukyat)**\n\n*1 {nama_bulan_saja} {tahun_hijriah} H Masuk Besok.*")
            else:
                st.error(f"❌ **STATUS: TIDAK MEMENUHI KRITERIA MABIMS (Istikmal)**\n\n*Bulan Berjalan Digenapkan 30 Hari. 1 {nama_bulan_saja} {tahun_hijriah} H Masuk Lusa.*")

            # Stellarium Web Embed
            st.markdown("---")
            st.subheader("🪐 Visualisasi Langit Interaktif (Stellarium Web Engine)")
            
            dt_sunset_utc = t_sunset.utc_datetime()
            iso_utc_stellarium = dt_sunset_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            stellarium_url = f"https://stellarium-web.org/skysource/Moon?lat=5.5483&lng=95.3238&date={iso_utc_stellarium}&fov=2.0"

            st.components.v1.iframe(stellarium_url, height=520)