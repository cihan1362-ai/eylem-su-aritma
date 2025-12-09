import streamlit as st
import pandas as pd
import yfinance as yf
from thefuzz import process

# --- 1. AYARLAR VE SABİT LİNK ---
# Google Sheets Linkini Buraya Yapıştır:
SABIT_LINK = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTRinIbcBwFoLk6WBoNZHTd0r1xnj5NTcyf98Ipig5Ns7xm_ieb8nndmR_pU-vawHepe1Y7NkytzQF_/pub?output=csv" 

st.set_page_config(page_title="Eylem Su Arıtma", page_icon="💧", layout="wide")
st.title("💧 Eylem Su Arıtma | Akıllı Üretim ve Maliyet")

# --- HAFIZA (SESSION STATE) ---
if 'sepet' not in st.session_state:
    st.session_state.sepet = pd.DataFrame(columns=["Ürün Adı", "Tedarikçi", "Adet", "Birim Maliyet ($+KDV)", "TL MALİYETİ"])

# --- 2. DOLAR KURU VE AYARLAR ---

# DÜZELTME: ttl=600 ekledik (10 dakikada bir yeniler)
@st.cache_data(ttl=600)
def dolar_kuru_getir():
    try:
        # DÜZELTME: interval="1m" ekledik (Dakikalık anlık veri çeker)
        ticker = yf.Ticker("TRY=X")
        data = ticker.history(period="1d", interval="1m")
        # En son dakikanın kapanış fiyatını al
        return data["Close"].iloc[-1]
    except:
        # İnternet yoksa veya veri çekemezse varsayılan
        return 34.50 

# Kuru hemen çek
guncel_kur = dolar_kuru_getir()

# Sidebar
st.sidebar.header("⚙️ Yönetim Paneli")

# Kur bilgisini göster
st.sidebar.info(f"💵 Canlı Kur: {guncel_kur:.4f} TL") # 4 hane gösterelim daha hassas olsun

# Manuel Müdahale İmkanı
manuel_kur = st.sidebar.number_input("Kur Ayarı", value=float(guncel_kur), format="%.4f", step=0.01)
kdv_orani = st.sidebar.number_input("KDV Oranı (%)", value=20.0, step=1.0)

st.sidebar.markdown("---")

# Butonlar
col_yenile, col_cop = st.sidebar.columns(2)

with col_yenile:
    if st.button("🔄 Kuru Yenile"):
        st.cache_data.clear() # Hafızayı sil
        st.rerun() # Sayfayı yenile (Yeni kur gelecek)

with col_cop:
    if st.button("🗑️ Sepeti Sil"):
        st.session_state.sepet = pd.DataFrame(columns=["Ürün Adı", "Tedarikçi", "Adet", "Birim Maliyet ($+KDV)", "TL MALİYETİ"])
        st.rerun()

# --- 3. VERİ HAZIRLIK ---
def veri_hazirla_ve_hesapla(df):
    def temizle(val):
        try:
            val = str(val).replace('$', '').replace('₺', '').replace(',', '.')
            return float(val)
        except:
            return 0.0
    
    df['Liste Fiyatı'] = df['Liste Fiyatı'].apply(temizle)
    
    def varsayilan_iskonto(tedarikci):
        t = str(tedarikci).lower()
        if "hsc" in t: return 55.0
        if "esli" in t: return 52.0
        return 0.0 
    
    df['İskonto (%)'] = df['Tedarikçi'].apply(varsayilan_iskonto)
    
    # Hesaplamalar
    df["Net ($)"] = df["Liste Fiyatı"] * (1 - (df["İskonto (%)"] / 100))
    df["Birim Maliyet ($+KDV)"] = df["Net ($)"] * (1 + (kdv_orani / 100))
    df["TL MALİYETİ"] = df["Birim Maliyet ($+KDV)"] * manuel_kur
    
    return df

# --- 4. ANA EKRAN ---

if len(SABIT_LINK) > 10:
    try:
        df_ham = pd.read_csv(SABIT_LINK, on_bad_lines='skip') 
        gerekli = ["Ürün Adı", "Tedarikçi", "Liste Fiyatı"]
        
        if all(col in df_ham.columns for col in gerekli):
            df_islenmis = veri_hazirla_ve_hesapla(df_ham)
            
            # --- ARAMA ALANI ---
            st.markdown("### 🔍 Ürün Bul ve Ekle")
            arama_metni = st.text_input("Hızlı Arama", placeholder="Örn: Siliphos, Membran...", label_visibility="collapsed")

            gosterilecek_df = pd.DataFrame()

            if arama_metni:
                tum_urun_isimleri = df_islenmis['Ürün Adı'].astype(str).tolist()
                eslesenler = process.extract(arama_metni, tum_urun_isimleri, limit=20)
                yakalanan_isimler = [x[0] for x in eslesenler if x[1] > 60]
                gosterilecek_df = df_islenmis[df_islenmis['Ürün Adı'].isin(yakalanan_isimler)].copy()
            else:
                gosterilecek_df = df_islenmis.head(5)

            # --- SEÇİM TABLOSU ---
            if not gosterilecek_df.empty:
                gosterilecek_df.insert(0, "Seç", False)
                
                edited_df = st.data_editor(
                    gosterilecek_df,
                    column_config={
                        "Seç": st.column_config.CheckboxColumn("Seç", default=False),
                        "Liste Fiyatı": st.column_config.NumberColumn("Liste ($)", format="$%.2f"),
                        "İskonto (%)": st.column_config.NumberColumn("İsk.", format="%d%%"),
                        "Birim Maliyet ($+KDV)": st.column_config.NumberColumn("Birim Maliyet ($)", format="$%.2f"),
                        "TL MALİYETİ": st.column_config.NumberColumn("Birim Maliyet (TL)", format="₺%.2f"),
                    },
                    disabled=["Ürün Adı", "Tedarikçi", "Liste Fiyatı", "Birim Maliyet ($+KDV)", "TL MALİYETİ", "İskonto (%)"],
                    hide_index=True,
                    use_container_width=True
                )
                
                # EKLEME BUTONU
                if st.button("⬇️ Seçilenleri Sepete Ekle"):
                    secilenler = edited_df[edited_df["Seç"] == True].copy()
                    if not secilenler.empty:
                        secilenler = secilenler.drop(columns=["Seç"])
                        secilenler["Adet"] = 1 
                        st.session_state.sepet = pd.concat([st.session_state.sepet, secilenler], ignore_index=True)
                        st.success("Ürünler sepete eklendi!")
                        st.rerun()

            st.divider()

            # --- SEPET VE ÜRETİM HESABI ---
            st.subheader("🛒 Üretim Sepeti (Adetleri Değiştir)")
            
            if not st.session_state.sepet.empty:
                st.session_state.sepet["Adet"] = st.session_state.sepet["Adet"].astype(int)
                st.session_state.sepet["Birim Maliyet ($+KDV)"] = st.session_state.sepet["Birim Maliyet ($+KDV)"].astype(float)
                st.session_state.sepet["TL MALİYETİ"] = st.session_state.sepet["TL MALİYETİ"].astype(float)

                sepet_son_hali = st.data_editor(
                    st.session_state.sepet,
                    column_config={
                        "Adet": st.column_config.NumberColumn("Adet", min_value=1, step=1),
                        "Ürün Adı": st.column_config.TextColumn("Ürün Adı", disabled=True),
                        "Birim Maliyet ($+KDV)": st.column_config.NumberColumn("Birim ($)", format="$%.2f", disabled=True),
                        "TL MALİYETİ": st.column_config.NumberColumn("Birim (TL)", format="₺%.2f", disabled=True),
                    },
                    column_order=["Adet", "Ürün Adı", "Tedarikçi", "Birim Maliyet ($+KDV)", "TL MALİYETİ"],
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    key="sepet_editor"
                )
                
                st.session_state.sepet = sepet_son_hali

                toplam_dolar = (st.session_state.sepet["Birim Maliyet ($+KDV)"] * st.session_state.sepet["Adet"]).sum()
                toplam_tl = (st.session_state.sepet["TL MALİYETİ"] * st.session_state.sepet["Adet"]).sum()
                toplam_parca = st.session_state.sepet["Adet"].sum()

                st.markdown("### 📊 Toplam Maliyet Özeti")
                c1, c2, c3 = st.columns(3)
                c1.metric("Toplam Parça", f"{toplam_parca} Adet")
                c2.metric("Toplam ($)", f"${toplam_dolar:.2f}")
                c3.metric("Toplam (TL)", f"₺{toplam_tl:.2f}")

            else:
                st.info("Sepetiniz boş.")

        else:
             st.error(f"Excel sütunları hatalı! {gerekli}")
    except Exception as e:
        st.error(f"Beklenmeyen hata: {e}")
else:
    st.warning("⚠️ Google Sheets linkini kodun içine yapıştırmayı unutma!")
