# Ziemia: źródła i wznowienie filmu

Cel: 60 sekund rzeczywistego ruchu w siedmiu fotorealistycznych ujęciach z lotu ptaka. Zatwierdzono **14 sekund**: osadę (8 s) i pożar lasu (6 s), zapisane w `../motion_sources/`. Brakuje **46 sekund**: dinozaurów, wycinki, mostu, przemysłu i współczesnego miasta. Starsze pliki filmowe w głównym katalogu nie oznaczają ukończenia tej wersji.

Stan limitu odczytany 28 października 2026: **94,781 s GPU**, przy wymaganej rezerwacji **150 s** dla jednego zadania. Serwis wskazał odnowienie **28 października 2026 około 12:59:45 czasu polskiego**. Przed każdym zadaniem skrypt ponownie odczytuje rzeczywisty limit. Nie ma zaplanowanego automatycznego wznowienia ani gwarancji ukończenia po jednym resecie.

[Obejrzyj fragment 14 sekund: pożar i budowa osady](../ziemia_ruch_fragment14s.mp4?raw=true). To montaż dwóch zatwierdzonych ujęć, bez powtarzania klatek; pełna minuta nadal wymaga brakującego materiału.

## Przygotowanie

Wymagane: Python 3.10+, FFmpeg/ffprobe z libx264 i filtrem drawtext, font Open Sans Light. Inną istniejącą czcionkę można wskazać zmienną `EARTHFILM_FONT`. W katalogu głównym repozytorium:

```sh
python3 -m venv film_pipeline/.venv
film_pipeline/.venv/bin/pip install -r film_pipeline/requirements.txt
```

`HF_TOKEN` musi być dostarczony jako sekret środowiska. Nie wklejaj jego wartości do kodu, poleceń, czatu ani plików repozytorium. Skrypt używa wyłącznie zweryfikowanego bezpłatnego konta osobistego i odmawia zadania, jeżeli limit nie wystarcza. Płatne generowanie nie jest dozwolone. Nie zmieniaj kont ani tożsamości w celu obchodzenia limitów.

## Kolejne ujęcia

`shots.json` opisuje długości, kadry startowe i prompty. Ścieżki w nim są względne wobec tego katalogu. Obrazy w `assets/` są wyłącznie klatkami startowymi dla modelu wideo; montaż nie zastępuje nimi brakującego ruchu.

Następne przygotowane zadanie to nowa próba mostu, uruchamiana z głównego katalogu repozytorium dopiero po odnowieniu limitu. Kadr startowy pokazuje istniejący most w trakcie budowy; nie jest wygenerowanym filmem:

```sh
film_pipeline/.venv/bin/python film_pipeline/generate_authenticated.py \
  --clip-id bridge_take2 \
  --image film_pipeline/assets/bridge_under_construction.png \
  --prompt film_pipeline/prompts/bridge_take2.txt \
  --duration 10 --width 1152 --height 640 --seed 20261031
```

Wynik trafia do `motion_sources/NAZWA/clip.mp4`. Skrypt nie nadpisuje istniejących filmów; odrzuconą próbę zachowaj i użyj nowej nazwy, np. `bridge_take2`. Dla mostu użyj przygotowanego `bridge_take2.txt` i nowego kadru startowego; starszy `bridge.txt` pochodzi z odrzuconej próby. Nowe wersje należy obejrzeć przed wyborem materiału końcowego.

Do zatwierdzenia potrzebny jest plik `qa.json` obok filmu: `approved: true`, dokładny `sha256` filmu i opis faktycznie obejrzanego ruchu. Przykłady są przy dwóch zatwierdzonych źródłach. Sam poprawny MP4 nie potwierdza jakości akcji. Odrzucaj zbliżenia i cięcia w środku ujęcia, samo przesuwanie kamery, znikanie lasu przez przenikanie oraz niespójnie zmieniające się budowle. Po przeglądzie umieść wybraną próbę razem z jej własnym `qa.json` w katalogu odpowiadającym nazwie z manifestu (`bridge`, `dinos` itd.). Nie zatwierdzaj plików automatycznie.

Metadane lokalnych prób (`request.json`, `result.json`, `error.json`, foldery pobrań klienta) nie są potrzebne do publikacji filmu. Nie dodawaj ich zbiorczo do repozytorium.

## Montaż i kontrola

```sh
python3 film_pipeline/assemble_motion.py --check-inputs
python3 film_pipeline/assemble_motion.py
```

Pierwsze polecenie obecnie prawidłowo kończy się błędem: brakuje pięciu ujęć. Montaż wymaga siedmiu źródeł z zatwierdzeniem związanym z SHA-256. Wynik `ziemia_motion.mp4` ma mieć dokładnie 60 s / 1440 klatek przy 24 fps, H.264 1280×720 i instrumentalną muzykę AAC. Skrypt sprawdza parametry i dekoduje cały eksport. Nie dopełnia braków pętlami, zatrzymanymi obrazami, spowolnieniem ani pokazem slajdów.
