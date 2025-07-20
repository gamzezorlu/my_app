import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
from io import BytesIO
import calendar
warnings.filterwarnings('ignore')

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="Doğalgaz Kaçak Kullanım Tespit Sistemi",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Doğalgaz Kaçak Kullanım Tespit Sistemi")
st.markdown("**Bina ortalaması karşılaştırması ve mevsimsel analiz ile gelişmiş kaçak tespit**")
st.markdown("---")

# Yardımcı fonksiyonlar
def is_winter_month(month_str):
    """Kış aylarını tespit et (Aralık, Ocak, Şubat, Mart)"""
    try:
        month_num = int(month_str.split('-')[0])
        return month_num in [12, 1, 2, 3]
    except:
        return False

def get_year_from_month(month_str):
    """Ay stringinden yıl bilgisini çıkar"""
    try:
        parts = month_str.split('-')
        return int(parts[1])
    except:
        return None

def calculate_building_averages(df, month_columns):
    """Bina bazında aylık ortalama tüketimleri hesapla"""
    building_averages = {}
    
    for month in month_columns:
        building_avg = df.groupby('BN')[month].mean().to_dict()
        building_averages[month] = building_avg
    
    return building_averages

def create_excel_report(suspicious_df, df, month_columns, building_averages):
    """Detaylı Excel raporu oluştur"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Ana rapor sayfası
        suspicious_df.to_excel(writer, sheet_name='Şüpheli Tesisatlar', index=False)
        
        # Detaylı analiz sayfası
        detailed_analysis = []
        for _, row in suspicious_df.iterrows():
            tn = row['TN']
            bn = row['BN']
            original_row = df[df['TN'] == tn].iloc[0]
            
            detail = {
                'TN': tn,
                'BN': bn,
                'Risk_Skoru': row['Risk_Skoru'],
                'Ortalama_Tuketim': row['Ortalama_Tuketim'],
                'Bina_Ortalamasi': row['Bina_Ortalama_Tuketim'],
                'Bina_Ortalamasindan_Sapma': row['Bina_Sapma_Yuzdesi'],
                'Kis_Riski': row['Kis_Anomali_Skoru'],
                'Anomali_Detay': row['Anomali_Detayi']
            }
            
            # Aylık veriler
            for month in month_columns:
                detail[f'Tuketim_{month}'] = original_row[month]
                if month in building_averages:
                    detail[f'BinaOrt_{month}'] = building_averages[month].get(bn, 0)
            
            detailed_analysis.append(detail)
        
        detailed_df = pd.DataFrame(detailed_analysis)
        detailed_df.to_excel(writer, sheet_name='Detaylı Analiz', index=False)
        
        # Bina bazında özet
        building_summary = suspicious_df.groupby('BN').agg({
            'TN': 'count',
            'Risk_Skoru': 'mean',
            'Ortalama_Tuketim': 'mean',
            'Kis_Anomali_Skoru': 'mean'
        }).reset_index()
        building_summary.columns = ['Bina_No', 'Susheli_Tesisat_Sayisi', 'Ortalama_Risk_Skoru', 'Ortalama_Tuketim', 'Ortalama_Kis_Riski']
        building_summary = building_summary.sort_values('Ortalama_Risk_Skoru', ascending=False)
        building_summary.to_excel(writer, sheet_name='Bina Bazında Özet', index=False)
    
    output.seek(0)
    return output.getvalue()

# Sidebar - Veri yükleme
with st.sidebar:
    st.header("📊 Excel Veri Yükleme")
    uploaded_file = st.file_uploader("Excel dosyası seçin (TN, BN, ay-yıl sütunları)", 
                                   type=['xlsx', 'xls'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.success(f"✅ {len(df)} kayıt yüklendi")
            
            # Veri yapısını kontrol et
            required_cols = ['TN', 'BN']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                st.error(f"❌ Eksik sütunlar: {', '.join(missing_cols)}")
                df = None
            else:
                # Ay sütunlarını tespit et
                month_columns = [col for col in df.columns if col not in ['TN', 'BN']]
                st.info(f"📅 {len(month_columns)} aylık veri tespit edildi")
                
        except Exception as e:
            st.error(f"❌ Dosya okuma hatası: {str(e)}")
            df = None
    else:
        # Demo veri oluştur
        st.info("Demo veri kullanılıyor")
        np.random.seed(42)
        n_records = 500
        n_buildings = 50
        
        # Tesisat ve bina numaraları
        tn_list = [f"TN{i:06d}" for i in range(1, n_records+1)]
        bn_list = [f"BN{i:04d}" for i in np.random.randint(1, n_buildings+1, n_records)]
        
        # 3 yıllık veri (2021-2023)
        months = []
        for year in [2021, 2022, 2023]:
            for month in range(1, 13):
                months.append(f"{month}-{year}")
        
        data = {'TN': tn_list, 'BN': bn_list}
        
        # Bina bazında ortalama tüketim seviyeleri
        building_base_consumption = {f"BN{i:04d}": np.random.normal(120, 30) 
                                   for i in range(1, n_buildings+1)}
        
        for month in months:
            month_num = int(month.split('-')[0])
            year = int(month.split('-')[1])
            
            # Sezonsal faktör
            if month_num in [12, 1, 2, 3]:  # Kış ayları
                seasonal_factor = 1.8
            elif month_num in [4, 5, 10, 11]:  # Geçiş ayları
                seasonal_factor = 1.2
            else:  # Yaz ayları
                seasonal_factor = 0.6
            
            consumption_values = []
            for i, bn in enumerate(bn_list):
                base = building_base_consumption[bn]
                # Normal tüketim
                normal = max(0, np.random.normal(base * seasonal_factor, base * 0.2))
                
                # Kaçak simülasyonu (%8 oranında)
                if np.random.random() < 0.08:
                    # Özellikle kış aylarında kaçak daha belirgin
                    reduction_factor = 0.4 if month_num in [12, 1, 2, 3] else 0.6
                    normal *= reduction_factor
                
                consumption_values.append(round(normal, 1))
            
            data[month] = consumption_values
        
        df = pd.DataFrame(data)
        month_columns = months

if 'df' in locals() and df is not None:
    # Ana analiz bölümü
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("⚙️ Analiz Parametreleri")
        
        col_param1, col_param2, col_param3 = st.columns(3)
        
        with col_param1:
            bina_sapma_esigi = st.slider("Bina Ort. Sapma Eşiği (%)", 10, 70, 30, 5)
            kis_dusus_esigi = st.slider("Kış Düşüş Eşiği (%)", 20, 80, 40, 5)
        
        with col_param2:
            min_months = st.slider("Min. Sürekli Ay", 2, 6, 3)
            min_consumption = st.slider("Min. Tüketim (m³)", 0, 100, 20)
        
        with col_param3:
            risk_threshold = st.slider("Rapor Risk Eşiği", 20, 80, 40, 5)
    
    with col2:
        st.header("📊 Veri Özeti")
        st.metric("Toplam Tesisat", len(df))
        st.metric("Toplam Bina", df['BN'].nunique())
        st.metric("Analiz Dönemi", f"{len(month_columns)} ay")
        st.metric("Ortalama Aylık Tüketim", f"{df[month_columns].mean().mean():.1f} m³")

    # Bina ortalamalarını hesapla
    building_averages = calculate_building_averages(df, month_columns)
    
    # Gelişmiş kaçak tespit analizi
    def advanced_leak_detection(df, month_columns, building_averages, 
                               bina_sapma_esigi, kis_dusus_esigi, min_months_param, 
                               min_cons, risk_threshold):
        results = []
        
        for idx, row in df.iterrows():
            tn = row['TN']
            bn = row['BN']
            consumptions = row[month_columns].values
            
            # Temel kontroller
            avg_consumption = np.mean(consumptions)
            if avg_consumption < min_cons:
                continue
            
            # Bina ortalaması ile karşılaştırma
            building_avg_consumptions = []
            for month in month_columns:
                building_avg_consumptions.append(building_averages[month].get(bn, avg_consumption))
            
            building_avg = np.mean(building_avg_consumptions)
            building_deviation = ((building_avg - avg_consumption) / building_avg * 100) if building_avg > 0 else 0
            
            # Kış ayları analizi
            winter_months = [(i, month) for i, month in enumerate(month_columns) if is_winter_month(month)]
            winter_years = {}
            
            # Yıl bazında kış ortalamalarını grupla
            for i, month in winter_months:
                year = get_year_from_month(month)
                if year:
                    if year not in winter_years:
                        winter_years[year] = []
                    winter_years[year].append(consumptions[i])
            
            # Kış yılları arası karşılaştırma
            winter_anomaly_score = 0
            winter_decline_years = 0
            winter_details = []
            
            if len(winter_years) >= 2:
                years = sorted(winter_years.keys())
                for i in range(1, len(years)):
                    prev_year_avg = np.mean(winter_years[years[i-1]])
                    curr_year_avg = np.mean(winter_years[years[i]])
                    
                    if prev_year_avg > min_cons:
                        decline_pct = (prev_year_avg - curr_year_avg) / prev_year_avg * 100
                        if decline_pct > kis_dusus_esigi:
                            winter_decline_years += 1
                            winter_anomaly_score += decline_pct
                            winter_details.append(f"{years[i]}:{decline_pct:.1f}%↓")
            
            # Genel anomali tespiti
            consecutive_low = 0
            max_consecutive = 0
            anomaly_months = []
            
            for i in range(1, len(consumptions)):
                prev_consumption = consumptions[i-1]
                curr_consumption = consumptions[i]
                
                if prev_consumption > min_cons:
                    drop_percentage = (prev_consumption - curr_consumption) / prev_consumption * 100
                    
                    # Bina ortalaması altında mı kontrol et
                    month_building_avg = building_averages[month_columns[i]].get(bn, 0)
                    below_building_avg = (curr_consumption < month_building_avg * (100 - bina_sapma_esigi) / 100)
                    
                    if drop_percentage > 25 or below_building_avg:
                        consecutive_low += 1
                        anomaly_months.append(month_columns[i])
                    else:
                        max_consecutive = max(max_consecutive, consecutive_low)
                        consecutive_low = 0
            
            max_consecutive = max(max_consecutive, consecutive_low)
            
            # Risk skoru hesaplama (0-100)
            risk_components = {
                'building_deviation': min(building_deviation, 50) * 1.5,  # Bina sapması
                'winter_anomaly': min(winter_anomaly_score, 100) * 0.8,   # Kış anomalisi  
                'consecutive_months': max_consecutive * 15,                # Süreklilik
                'winter_decline_years': winter_decline_years * 20         # Yıllık kış düşüşü
            }
            
            total_risk = sum(risk_components.values())
            risk_score = min(total_risk, 100)
            
            # Anomali detayı
            anomaly_detail_parts = []
            if building_deviation > bina_sapma_esigi:
                anomaly_detail_parts.append(f"Bina ort. %{building_deviation:.1f} altında")
            if winter_decline_years > 0:
                anomaly_detail_parts.append(f"Kış düşüşü: {', '.join(winter_details)}")
            if max_consecutive >= min_months_param:
                anomaly_detail_parts.append(f"{max_consecutive} ay sürekli düşük")
            
            anomaly_detail = " | ".join(anomaly_detail_parts)
            
            # Şüpheli durumu değerlendir
            is_suspicious = (
                risk_score >= risk_threshold and
                (building_deviation > bina_sapma_esigi or 
                 winter_decline_years > 0 or 
                 max_consecutive >= min_months_param)
            )
            
            if is_suspicious:
                results.append({
                    'TN': tn,
                    'BN': bn,
                    'Risk_Skoru': round(risk_score, 1),
                    'Ortalama_Tuketim': round(avg_consumption, 1),
                    'Bina_Ortalama_Tuketim': round(building_avg, 1),
                    'Bina_Sapma_Yuzdesi': round(building_deviation, 1),
                    'Kis_Anomali_Skoru': round(winter_anomaly_score, 1),
                    'Kis_Dusus_Yil_Sayisi': winter_decline_years,
                    'Surekli_Dusuk_Ay': max_consecutive,
                    'Anomali_Detayi': anomaly_detail,
                    'Oncelik': 'YÜKSEK' if risk_score > 70 else 'ORTA' if risk_score > 50 else 'DÜŞÜK'
                })
        
        return pd.DataFrame(results).sort_values('Risk_Skoru', ascending=False)

    # Analizi çalıştır
    with st.spinner('Gelişmiş kaçak kullanım analizi yapılıyor...'):
        suspicious_df = advanced_leak_detection(
            df, month_columns, building_averages, 
            bina_sapma_esigi, kis_dusus_esigi, min_months, 
            min_consumption, risk_threshold
        )
    
    st.markdown("---")
    st.header("🚨 Kaçak Kullanım Şüpheli Tesisatlar")
    
    if len(suspicious_df) > 0:
        # Özet istatistikler
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Şüpheli Tesisat", len(suspicious_df), 
                     f"{len(suspicious_df)/len(df)*100:.1f}%")
        with col2:
            yuksek_risk = len(suspicious_df[suspicious_df['Risk_Skoru'] > 70])
            st.metric("Yüksek Risk", yuksek_risk)
        with col3:
            kis_anomalisi = len(suspicious_df[suspicious_df['Kis_Dusus_Yil_Sayisi'] > 0])
            st.metric("Kış Anomalisi", kis_anomalisi)
        with col4:
            bina_anomalisi = len(suspicious_df[suspicious_df['Bina_Sapma_Yuzdesi'] > bina_sapma_esigi])
            st.metric("Bina Ort. Altı", bina_anomalisi)
        
        # Risk skoruna göre renklendirme
        def color_risk_row(row):
            risk = row['Risk_Skoru']
            if risk > 70:
                return ['background-color: #ffebee'] * len(row)
            elif risk > 50:
                return ['background-color: #fff3e0'] * len(row)
            else:
                return ['background-color: #e8f5e8'] * len(row)
        
        # Öncelik sırasına göre filtre
        priority_filter = st.selectbox(
            "Öncelik Filtresi:", 
            ['TÜM', 'YÜKSEK', 'ORTA', 'DÜŞÜK'],
            index=0
        )
        
        if priority_filter != 'TÜM':
            display_df = suspicious_df[suspicious_df['Oncelik'] == priority_filter]
        else:
            display_df = suspicious_df
        
        # Tabloyu göster
        styled_df = display_df.style.apply(color_risk_row, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Excel raporu indirme
        st.markdown("---")
        st.header("📥 Detaylı Excel Raporu İndir")
        
        if st.button("📊 Excel Raporu Oluştur", type="primary"):
            with st.spinner('Excel raporu hazırlanıyor...'):
                excel_data = create_excel_report(suspicious_df, df, month_columns, building_averages)
                
                st.download_button(
                    label="📊 Detaylı Excel Raporu İndir",
                    data=excel_data,
                    file_name=f"dogalgaz_kacak_raporu_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success("✅ Excel raporu hazır! İndir butonuna tıklayın.")
        
        # Grafikler
        st.header("📊 Görsel Analizler")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Risk Analizi", "Bina Karşılaştırma", "Kış Analizi", "Tesisat Detay"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                # Risk dağılımı
                fig = px.histogram(suspicious_df, x='Risk_Skoru', nbins=15,
                                 title='Risk Skoru Dağılımı')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Öncelik dağılımı
                priority_counts = suspicious_df['Oncelik'].value_counts()
                fig = px.pie(values=priority_counts.values, names=priority_counts.index,
                           title='Öncelik Dağılımı')
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            # En çok şüpheli tesisata sahip binalar
            building_counts = suspicious_df['BN'].value_counts().head(10)
            
            fig = px.bar(x=building_counts.index, y=building_counts.values,
                        title='En Çok Şüpheli Tesisata Sahip Binalar (Top 10)')
            fig.update_layout(xaxis_title='Bina No', yaxis_title='Şüpheli Tesisat Sayısı')
            st.plotly_chart(fig, use_container_width=True)
            
            # Bina bazında ortalama risk
            building_risk = suspicious_df.groupby('BN')['Risk_Skoru'].mean().head(10)
            fig = px.bar(x=building_risk.index, y=building_risk.values,
                        title='En Yüksek Risk Skoru Ortalamасına Sahip Binalar')
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            # Kış anomali analizi
            winter_anomaly = suspicious_df[suspicious_df['Kis_Dusus_Yil_Sayisi'] > 0]
            
            if len(winter_anomaly) > 0:
                fig = px.scatter(winter_anomaly, x='Kis_Anomali_Skoru', y='Risk_Skoru',
                               size='Kis_Dusus_Yil_Sayisi', hover_data=['TN', 'BN'],
                               title='Kış Anomalisi vs Risk Skoru')
                st.plotly_chart(fig, use_container_width=True)
                
                st.write("**Kış aylarında yüksek düşüş gösteren tesisatlar:**")
                winter_top = winter_anomaly.nlargest(5, 'Kis_Anomali_Skoru')[['TN', 'BN', 'Kis_Anomali_Skoru', 'Anomali_Detayi']]
                st.dataframe(winter_top, use_container_width=True)
            else:
                st.info("Kış anomalisi tespit edilen tesisat bulunamadı.")
        
        with tab4:
            # Belirli tesisatın detaylı analizi
            selected_tn = st.selectbox("Detaylı analiz için tesisat seçin:", suspicious_df['TN'].tolist())
            
            if selected_tn:
                selected_row = df[df['TN'] == selected_tn].iloc[0]
                selected_info = suspicious_df[suspicious_df['TN'] == selected_tn].iloc[0]
                
                consumption_data = selected_row[month_columns].values
                bn = selected_row['BN']
                
                # Bina ortalaması verisi
                building_data = [building_averages[month].get(bn, 0) for month in month_columns]
                
                fig = go.Figure()
                
                # Tesisat tüketimi
                fig.add_trace(go.Scatter(
                    x=month_columns, y=consumption_data,
                    mode='lines+markers', name='Tesisat Tüketimi',
                    line=dict(color='blue', width=2)
                ))
                
                # Bina ortalaması
                fig.add_trace(go.Scatter(
                    x=month_columns, y=building_data,
                    mode='lines+markers', name='Bina Ortalaması',
                    line=dict(color='red', width=2, dash='dash')
                ))
                
                # Kış aylarını vurgula
                for i, month in enumerate(month_columns):
                    if is_winter_month(month):
                        fig.add_vrect(
                            x0=i-0.4, x1=i+0.4,
                            fillcolor="lightblue", opacity=0.2,
                            layer="below", line_width=0
                        )
                
                fig.update_layout(
                    title=f'Tesisat {selected_tn} - Detaylı Tüketim Analizi',
                    xaxis_title='Ay', yaxis_title='Tüketim (m³)',
                    xaxis_tickangle=-45
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tesisat bilgileri
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Risk Skoru", selected_info['Risk_Skoru'])
                with col2:
                    st.metric("Bina Sapma", f"{selected_info['Bina_Sapma_Yuzdesi']:.1f}%")
                with col3:
                    st.metric("Kış Anomali", selected_info['Kis_Anomali_Skoru'])
                with col4:
                    st.metric("Öncelik", selected_info['Oncelik'])
                
                st.info(f"**Anomali Detayı:** {selected_info['Anomali_Detayi']}")
        
    else:
        st.info("Belirtilen kriterlere göre şüpheli tesisat bulunamadı.")
        st.balloons()

else:
    st.info("Lütfen Excel veri dosyanızı yükleyin.")
    st.markdown("""
    ### 📋 Beklenen Veri Formatı:
    - **TN**: Tesisat numarası (örn: TN000001)
    - **BN**: Bina numarası (örn: BN0001)  
    - **1-2021, 2-2021, ...**: Aylık tüketim değerleri (m³)
    """)

# Alt bilgi
st.markdown("---")
st.markdown("""
### 🎯 **Gelişmiş Analiz Metodolojisi**

**1. Bina Ortalaması Karşılaştırması:**
- Her tesisat kendi binasındaki diğer tesisatların ortalaması ile karşılaştırılır
- Bina ortalamasından belirli eşik altında kalanlar işaretlenir

**2. Mevsimsel (Kış) Analiz:**
- Kış ayları (Aralık, Ocak, Şubat, Mart) özel olarak analiz edilir
- Önceki kış dönemlerine göre anormal düşüşler tespit edilir
- Yıl bazında kış ortalamaları karşılaştırılır

**3. Risk Skoru Bileşenleri:**
- Bina ortalamasından sapma (%50 ağırlık)
- Kış ayları anomali skoru (%30 ağırlık)  
- Sürekli düşük ay sayısı (%20 ağırlık)

**4. Excel Raporu İçeriği:**
- **Sayfa 1:** Şüpheli tesisatlar özet listesi
- **Sayfa 2:** Detaylı analiz (aylık veriler + bina karşılaştırması)
- **Sayfa 3:** Bina bazında özet rapor

⚠️ **Önemli:** Bu analiz ön değerlendirme içindir. Kesin karar için mutlaka saha kontrolü yapılmalıdır.
""")
