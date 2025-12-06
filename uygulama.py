import streamlit as st
import pandas as pd
import yfinance as yf

# --- 1. AYARLAR VE SABİT LİNK ---
# BURAYA KENDİ LİNKİNİ YAPIŞTIRMAYI UNUTMA!
SABIT_LINK = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTRinIbcBwFoLk6WBoNZHTd0r1xnj5NTcyf98Ipig5Ns7xm_ieb8nndmR_pU-vawHepe1Y7NkytzQF_/pub?output=csv" 

st.set_page_config(page_title="Eylem Su Arıtma", page_icon="💧", layout="wide")
st.title("💧 Eylem Su Arıtma Sistemleri | Akıllı Maliyet Yönetimi")

# --- 2. DOLAR KURU VE AYARLAR ---
@st.cache_data
def dolar_kuru_getir():
    try:
        ticker = yf.Ticker("TRY=X")
        data = ticker.history(period="1d")
        return data["Close"].iloc[-1]
    except:
        return 34.50 

guncel_kur = dolar_kuru_getir()

# Sidebar
st.sidebar.header("⚙️ Yönetim Paneli")
st.sidebar.info(f"💵 Canlı Kur: {guncel_kur:.2f} TL")
manuel_kur = st.sidebar.number_input("Kur Ayarı", value=float(guncel_kur), step=0.01)
kdv_orani = st.sidebar.number_input("KDV Oranı (%)", value=20.0, step=1.0)
st.sidebar.divider()
if st.sidebar.button("🔄 Verileri Yenile"):
    st.cache_data.clear()
    st.rerun()

# --- 3. VERİ HAZIRLIK ---
def veri_hazirla(df):
    def temizle(val):
        try:
            val = str(val).replace('$', '').replace('₺', '').replace(',', '.')
            return float(val)
        except:
            return 0.0
    
    df['Liste Fiyatı'] = df['Liste Fiyatı'].apply(temizle)
    
    # Varsayılan İskontolar
    def varsayilan_iskonto(tedarikci):
        t = str(tedarikci).lower()
        if "hsc" in t: return 55.0
        if "esli" in t: return 52.0
        return 0.0 
    
    df['İskonto (%)'] = df['Tedarikçi'].apply(varsayilan_iskonto)
    return df

# --- 4. ANA EKRAN ---

if len(SABIT_LINK) > 10:
    try:
        df_ham = pd.read_csv(SABIT_LINK)
        gerekli = ["Ürün Adı", "Tedarikçi", "Liste Fiyatı"]
        
        if all(col in df_ham.columns for col in gerekli):
            df_islenmis = veri_hazirla(df_ham)
            df_islenmis.insert(0, "Seç", False)
            
            # --- BÜYÜK ARAMA ALANI (REVİZE EDİLDİ) ---
            st.markdown("### 🔍 Hızlı Ürün Arama")
            
            # Arama kutusunu daha belirgin yapmak için columns kullandık
            col_ara, col_bos = st.columns([3, 1]) 
            with col_ara:
                arama_metni = st.text_input(
                    "Arama", 
                    placeholder="Ürün adı yazın... (Örn: Membran, Post Karbon)", 
                    label_visibility="collapsed" # Başlığı gizle, sadece kutu görünsün
                )
            
            # --- FİLTRELEME MANTIĞI ---
            if arama_metni:
                # Sadece aranan kelimeyi içerenleri göster
                gosterilecek_df = df_islenmis[
                    df_islenmis['Ürün Adı'].astype(str).str.contains(arama_metni, case=False, na=False)
                ]
            else:
                # Arama yoksa hepsini göster
                gosterilecek_df = df_islenmis

            # --- TABLO ---
            st.write(f"Toplam **{len(gosterilecek_df)}** ürün listeleniyor.")
            
            edited_df = st.data_editor(
                gosterilecek_df,
                column_config={
                    "Seç": st.column_config.CheckboxColumn("Ekle", default=False),
                    "Liste Fiyatı": st.column_config.NumberColumn("Liste ($)", format="$%.2f", disabled=True),
                    "İskonto (%)": st.column_config.NumberColumn("İskonto (%)", min_value=0, max_value=100, step=1),
                    "Tedarikçi": st.column_config.TextColumn(disabled=True),
                    "Ürün Adı": st.column_config.TextColumn(disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                height=500,
                key="urun_tablosu" # Bu anahtar hafıza karışıklığını önler
            )

            # --- HESAPLAMA ---
            # Sadece ekranda görünen (filtrelenmiş) veriler üzerinden hesaplama yapar
            edited_df["Net ($)"] = edited_df["Liste Fiyatı"] * (1 - (edited_df["İskonto (%)"] / 100))
            edited_df["Maliyet ($+KDV)"] = edited_df["Net ($)"] * (1 + (kdv_orani / 100))
            edited_df["TL MALİYETİ"] = edited_df["Maliyet ($+KDV)"] * manuel_kur

            # --- SONUÇ PANELİ ---
            secilenler = edited_df[edited_df["Seç"] == True]

            if not secilenler.empty:
                st.markdown("---")
                st.subheader("🛠️ Eylem Su Arıtma | Set Maliyet Özeti")
                
                c1, c2, c3 = st.columns(3)
                toplam_dolar = secilenler["Maliyet ($+KDV)"].sum()
                toplam_tl = secilenler["TL MALİYETİ"].sum()
                
                c1.metric("Parça Sayısı", f"{len(secilenler)} Adet")
                c2.metric("Toplam Dolar", f"${toplam_dolar:.2f}")
                c3.metric("Toplam TL", f"₺{toplam_tl:.2f}")
                
                with st.expander("Detaylı Döküm (Tıkla Gör)"):
                    detay = secilenler[["Ürün Adı", "Tedarikçi", "İskonto (%)", "TL MALİYETİ"]].copy()
                    detay["TL MALİYETİ"] = detay["TL MALİYETİ"].apply(lambda x: f"₺{x:.2f}")
                    st.dataframe(detay, use_container_width=True)

        else:
             st.error(f"Excel başlıkları hatalı! {gerekli}")
    except Exception as e:
        st.error(f"Link Hatası: {e}")
else:
    st.warning("⚠️ Lütfen kodun içindeki SABIT_LINK kısmına Google Sheets linkini yapıştır.")