import streamlit as st
import pandas as pd
import yfinance as yf
from thefuzz import process # Akıllı arama kütüphanesi

# --- 1. AYARLAR VE SABİT LİNK ---
# Google Sheets Linkini Buraya Yapıştır:
SABIT_LINK = "https://docs.google.com/spreadsheets/d/e/............./pub?output=csv" 

st.set_page_config(page_title="Eylem Su Arıtma", page_icon="💧", layout="wide")
st.title("💧 Eylem Su Arıtma | Akıllı Maliyet ve Teklif")

# --- HAFIZA (SESSION STATE) ---
# Sepetin kaybolmaması için hafıza oluşturuyoruz
if 'sepet' not in st.session_state:
    st.session_state.sepet = pd.DataFrame()

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

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Sepeti ve Hafızayı Temizle"):
    st.session_state.sepet = pd.DataFrame()
    st.rerun()

# --- 3. VERİ HAZIRLIK VE HESAPLAMA ---
def veri_hazirla_ve_hesapla(df):
    # Temizlik
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
    
    # --- TÜM HESAPLAMALARI BAŞTAN YAP ---
    # Böylece listede direkt net fiyatları görürsün
    df["Net ($)"] = df["Liste Fiyatı"] * (1 - (df["İskonto (%)"] / 100))
    df["Birim Maliyet ($+KDV)"] = df["Net ($)"] * (1 + (kdv_orani / 100))
    df["TL MALİYETİ"] = df["Birim Maliyet ($+KDV)"] * manuel_kur
    
    return df

# --- 4. ANA EKRAN ---

if len(SABIT_LINK) > 10:
    try:
        df_ham = pd.read_csv(SABIT_LINK)
        gerekli = ["Ürün Adı", "Tedarikçi", "Liste Fiyatı"]
        
        if all(col in df_ham.columns for col in gerekli):
            df_islenmis = veri_hazirla_ve_hesapla(df_ham)
            
            # --- BÜYÜK ARAMA ALANI ---
            st.markdown("### 🔍 Akıllı Ürün Arama")
            arama_metni = st.text_input("Ürün Ara", placeholder="Örn: Siliphos, Membran (Hatalı yazsanız bile bulur)", label_visibility="collapsed")

            gosterilecek_df = pd.DataFrame()

            if arama_metni:
                # 1. AKILLI ARAMA (FUZZY SEARCH)
                tum_urun_isimleri = df_islenmis['Ürün Adı'].astype(str).tolist()
                
                # En iyi eşleşenleri bul (Skor 60 üzerindeyse getir)
                eslesenler = process.extract(arama_metni, tum_urun_isimleri, limit=20)
                yakalanan_isimler = [x[0] for x in eslesenler if x[1] > 60]
                
                # Tabloyu filtrele
                gosterilecek_df = df_islenmis[df_islenmis['Ürün Adı'].isin(yakalanan_isimler)].copy()
            else:
                # Arama yoksa ilk 10 ürünü göster (Hepsini gösterme, kafa karışmasın)
                gosterilecek_df = df_islenmis.head(10)
                if not arama_metni:
                     st.caption("💡 *Tüm listeyi görmemek için sadece arama sonuçları gösterilir. Yukarıya bir şeyler yazın.*")

            # --- ARAMA SONUÇLARI TABLOSU ---
            if not gosterilecek_df.empty:
                gosterilecek_df.insert(0, "Seç", False)
                
                # Tabloyu Göster (Hesaplanmış Fiyatlarla)
                edited_df = st.data_editor(
                    gosterilecek_df,
                    column_config={
                        "Seç": st.column_config.CheckboxColumn("Seç", default=False),
                        "Liste Fiyatı": st.column_config.NumberColumn("Liste ($)", format="$%.2f"),
                        "İskonto (%)": st.column_config.NumberColumn("İsk. (%)", format="%d"),
                        "Birim Maliyet ($+KDV)": st.column_config.NumberColumn("Maliyet ($)", format="$%.2f"),
                        "TL MALİYETİ": st.column_config.NumberColumn("Maliyet (TL)", format="₺%.2f"),
                    },
                    disabled=["Ürün Adı", "Tedarikçi", "Liste Fiyatı", "Birim Maliyet ($+KDV)", "TL MALİYETİ"],
                    hide_index=True,
                    use_container_width=True
                )
                
                # EKLE BUTONU
                col_btn, col_info = st.columns([1, 4])
                if col_btn.button("⬇️ Seçilenleri Sepete Ekle"):
                    secilenler = edited_df[edited_df["Seç"] == True]
                    if not secilenler.empty:
                        # Seçilenleri hafızaya (session_state) ekle
                        temiz_secilenler = secilenler.drop(columns=["Seç"]) # Seç kutusunu kaldır
                        st.session_state.sepet = pd.concat([st.session_state.sepet, temiz_secilenler], ignore_index=True)
                        st.success(f"{len(secilenler)} ürün sepete eklendi!")
                        st.rerun() # Sayfayı yenile ki sepet güncellensin
            
            st.divider()

            # --- SEPETİM (TOPLANAN ÜRÜNLER) ---
            st.subheader("🛒 Oluşturulan Set / Sepet")
            
            if not st.session_state.sepet.empty:
                # Sepeti Göster
                sepet_df = st.data_editor(
                    st.session_state.sepet,
                    column_config={
                        "Liste Fiyatı": st.column_config.NumberColumn("Liste ($)", format="$%.2f"),
                        "İskonto (%)": st.column_config.NumberColumn("İsk. (%)", format="%d"),
                        "Birim Maliyet ($+KDV)": st.column_config.NumberColumn("Maliyet ($)", format="$%.2f"),
                        "TL MALİYETİ": st.column_config.NumberColumn("Maliyet (TL)", format="₺%.2f"),
                    },
                    disabled=True, # Sepet artık salt okunur olsun
                    hide_index=True,
                    use_container_width=True,
                    key="sepet_tablosu"
                )
                
                # TOPLAMLAR
                toplam_dolar = st.session_state.sepet["Birim Maliyet ($+KDV)"].sum()
                toplam_tl = st.session_state.sepet["TL MALİYETİ"].sum()
                adet = len(st.session_state.sepet)

                c1, c2, c3 = st.columns(3)
                c1.metric("Toplam Parça", f"{adet} Adet")
                c2.metric("Toplam Maliyet ($)", f"${toplam_dolar:.2f}")
                c3.metric("Toplam Maliyet (TL)", f"₺{toplam_tl:.2f}")

            else:
                st.info("Sepetiniz boş. Yukarıdan ürün arayıp ekleyebilirsiniz.")

        else:
             st.error(f"Excel başlıkları hatalı! {gerekli}")
    except Exception as e:
        st.error(f"Hata: {e}")
else:
    st.warning("⚠️ Lütfen kodun içindeki SABIT_LINK kısmına Google Sheets linkini yapıştır.")
