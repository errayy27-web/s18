# SS OIL – PC merkezli ortak veri sistemi

Bu ZIP, mevcut S15 Flutter ekranlarını korur. Codemagic `codemagic.yaml` dosyası değiştirilmemiştir.

## Yeni eklenenler

- PC sunucusu kendi klasöründe `SSOIL_MERKEZ.db` adında **ayrı bir SQLite veritabanı** oluşturur. Mevcut kasa SQL veritabanına yazmaz.
- Etiketler, sipariş miktarları, tedarikçiler, ürün-tedarikçi eşlemesi ve minimum stok seviyeleri PC merkezinde kaydedilir; telefonlar 8 saniyede bir değişiklikleri almayı dener.
- Telefon çevrimdışıyken işlemler cihazda kuyruğa alınır ve sunucuya bağlanınca gönderilir.
- PC her 30 saniyede `SmP_S` toplamlarını salt-okunur sorgularla kontrol eder, değişen miktarları `sales_daily` tablosunda tutar. İlk taramada eski satışlar geçmiş günlere dağıtılmaz. PC kapalıyken gerçekleşen satışlar açıldığı günün farkına yazılabilir; bu gerçek tarih garantisi değildir.
- Yeni API: `GET /shared?since=0`, `POST /shared`, `GET /daily-sales`. Önceki `/snapshot`, `/sales`, `/kasa` gibi uç noktalar korunmuştur.

## PC kurulum

1. `pc_server` klasörünü kasa PC'sine kopyalayın.
2. Python 3 kurulu olmalı; `pip install pyodbc` komutunu çalıştırın. Windows SQL Server ODBC sürücüsü ayrıca kurulu olmalıdır.
3. `AYARLAR_ORNEK.bat` dosyasını `AYARLAR.bat` olarak kopyalayın. Gerçek **salt-okunur** SQL bağlantı ayarlarını ve güçlü, rastgele `SSOIL_API_TOKEN` değerini girin. `AYARLAR.bat` dosyasını GitHub'a yüklemeyin.
4. `BASLAT.bat` çalıştırın. Sunucu `8766` portunda dinler. PC üzerinde `SSOIL_MERKEZ.db` oluşur.
5. Telefon Ayarlar ekranında yerel API `http://PC_IP:8766` ve aynı token olmalı. İki telefon da bu PC'ye erişebildiğinde ortak kayıtlar eşitlenir.

## Farklı ağdan erişim

**Bu ZIP bulut sunucusu/VPN kurmaz.** Farklı ağda erişim için telefonlarla PC arasında kimlik doğrulamalı bir VPN (ör. Tailscale) veya güvenli HTTPS bulut geçidi ayrıca kurulmalıdır. **8766 portunu internete doğrudan açmayın**; HTTP ve token kullanıldığı için internete açık kullanım güvenli değildir.

## Bilinen sınırlar

- Aynı sipariş kalemini iki telefon eşzamanlı değiştirirse **son ulaşan işlem geçerli olur**. Bu sürümde gerçek çatışma çözümü ve iki kullanıcının sayım miktarlarını güvenle toplama henüz uygulanmamıştır.
- Ortak stok sayım oturumu ve fotoğrafların cihazlar arasında paylaşımı **henüz uygulanmadı**. Fotoğraflar mevcut sürümde telefonda kalır.
- Kasa SQL bağlantısı ve yakıt ART ID eşlemesi gerçek PC üzerinde doğrulanmalıdır.
- Uygulama Flutter derleyicisi ile bu ortamda APK'ya derlenemedi; Python merkezi veritabanı için üç otomatik test geçti.
- `SSOIL_MERKEZ.db` dosyasını düzenli olarak yedekleyin; sunucu kapalıyken dosyanın güvenli kopyasını almak en kolay yöntemdir.
