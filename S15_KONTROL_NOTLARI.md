# SS OIL S15 - kontrol ve sınırlar

- Codemagic: Kullanıcının çalıştığını doğruladığı yönteme dönüldü; `instance_type` yok, Flutter Android scaffold derleme sırasında üretiliyor, debug APK çıktısı alınıyor.
- Uygulama: Ayrı Ana Sayfa / Kasa / Stok / Siparişler / Çok Satanlar / Raporlar / Ayarlar sayfaları, siyah-sarı tema ve SS OIL logosu korunuyor.
- Kasa: SQL `SmP_Z` nakit/kart; `Povracaj` nakitten düşülüyor, ekranda iade satırı yok. Dopuna doğrulanmazsa toplam nakit tahmin edilmez.
- Etiket Yok: Ürün etiket listesine eklenir. Ürün fotoğrafı kamera/galeriden yerel kaydedilir.
- Son 7 gün: Telefondaki satış sayacı farkları saklanır; sekizinci günde eski gün silinir. Uygulama kapalıyken gerçekleşen satışlar, sunucu tarihli olay akışı sağlamadığından gerçek günlerine ayrılamaz.
- Yakıt/market ciro: Ürün grubu tanımı ve fiş bazlı gerçek fiyat olmadan günlük sayaç farkı * güncel fiyat yalnızca tahmindir; ekranda açıkça 'yerel tahmin' yazılır.
- Yakıt stokları: Ürün ART ID eşleşmesi ve başlangıç anı satış sayaçları doğruysa düşülür. Henüz gerçek sunucuda test edilmedi.
- Dopuna: PC'deki gerçek db3 yollarına erişim, tablo tarih ve status değerleri sunucuda doğrulanmalıdır.
- Test: Python sözdizimi ve YAML parse kontrol edildi; Flutter/Android derleme ve gerçek SQL/db3 testi bu ortamda yapılamadı.
