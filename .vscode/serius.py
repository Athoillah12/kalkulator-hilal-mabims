import streamlit as st
import datetime
from skyfield.api import load, wgs84
from skyfield import almanac

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

# DEFINISI KOORDINAT BANDA ACEH
aceh_geo = wgs84.latlon(5.5483, 95.3238)
aceh_location = earth + aceh_geo

st.sidebar.header("🗓️ Input Perkiraan Bulan")
tahun_input = st.sidebar.number_input("Tahun Masehi:", min_value=2024, max_value=2030, value=2026)
bulan_input = st.sidebar.slider("Bulan Masehi (Perkiraan Ijtima'):", 1, 12, 2)

if st.sidebar.button("Hitung Hilal Otomatis"):
    with st.spinner("Menghitung Ijtima', Hari Rukyat, Sunset, dan Posisi Hilal..."):
        # -------------------------------------------------------------
        # LANGKAH 1: Cari Waktu Ijtima' & Tentukan Hari Rukyat
        # -------------------------------------------------------------
        t0 = ts.utc(tahun_input, bulan_input, 1)
        t1 = ts.utc(tahun_input + 1, 1, 1) if bulan_input == 12 else ts.utc(tahun_input, bulan_input + 1, 1)

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
            # Rukyat dilakukan besok HANYA JIKA ijtima' terjadi SETELAH sunset pada hari yang sama (antara Sunset s.d. 23:59 WIB)
            if (dt_ijtima_wib.time() > dt_sunset_ij_wib.time()) and (dt_ijtima_wib.date() == dt_sunset_ij_wib.date()):
                dt_rukyat_date = dt_ijtima_wib.date() + datetime.timedelta(days=1)
                catatan_rukyat = "⚠️️ Ijtima' terjadi setelah sunset (antara Sunset - 23:59 WIB). Observasi rukyat dilakukan keesokan harinya."
            else:
                dt_rukyat_date = dt_ijtima_wib.date()
                catatan_rukyat = "ℹ️ Ijtima' terjadi antara jam 00:00 s.d. Sunset. Observasi rukyat dilakukan pada hari ijtima' tersebut."

            # -------------------------------------------------------------
            # LANGKAH 2: Cari Waktu Sunset (-0°16') pada HARI RUKYAT
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
                t_sunset = ts.utc(dt_rukyat_date.year, dt_rukyat_date.month, dt_rukyat_date.day, 11, 45) # Fallback UTC

            dt_sunset_wib = t_sunset.utc_datetime() + datetime.timedelta(hours=7)

            # -------------------------------------------------------------
            # LANGKAH 3: Ambil Tinggi Hilal & Elongasi pada Saat Sunset
            # -------------------------------------------------------------
            ast_moon = aceh_location.at(t_sunset).observe(moon).apparent()
            ast_sun = aceh_location.at(t_sunset).observe(sun).apparent()

            tinggi_hilal = ast_moon.altaz()[0].degrees
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

            if is_mabims:
                st.success("✅ **STATUS: MEMENUHI KRITERIA MABIMS (Imkanur Rukyat)**\n\n*Awal Bulan Hijriah Masuk Besok.*")
            else:
                st.error("❌ **STATUS: TIDAK MEMENUHI KRITERIA MABIMS (Istikmal)**\n\n*Bulan Berjalan Digenapkan 30 Hari.*")

            # Stellarium Web Embed (Format Jam UTC Murni)
            st.markdown("---")
            st.subheader("🪐 Visualisasi Langit Interaktif (Stellarium Web Engine)")
            
            dt_sunset_utc = t_sunset.utc_datetime()
            iso_utc_stellarium = dt_sunset_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            stellarium_url = f"https://stellarium-web.org/skysource/Moon?lat=5.5483&lng=95.3238&date={iso_utc_stellarium}&fov=2.0"

            st.iframe(stellarium_url, height=520)