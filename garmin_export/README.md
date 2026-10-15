# Garmin Export (QGIS-plugin)

Exporterar vektorlager från QGIS till äldre, **icke-Android** Garmin-enheter
(eTrex, GPSMAP 60/62/64, Oregon, Dakota, Montana, Colorado …).

Plugin:et automatiserar arbetsflödet i GPSFileDepots tutorial
*How to create Garmin topo maps* – lager → Polish Format (`.mp`) i rutor →
kompilering till `.img` – men med **mkgmap** i stället för cGPSmapper/Windows-
batchfiler, så det fungerar på Linux, macOS och Windows.

## Två exportvägar

| Flik | Resultat | Passar för |
|---|---|---|
| **Garmin map (IMG)** | `gmapsupp.img` (+ ev. `.tdb` för BaseCamp/MapSource) | Linjer, polygoner, POI:er som riktig karta på enheten |
| **GPX** | `.gpx` med waypoints / spår / rutter | Punkter och spår som ska ligga *ovanpå* kartan |

## Krav (endast för IMG)

* Java 8 eller nyare (`java` i PATH eller ange sökväg i dialogen)
* `mkgmap.jar` från <https://www.mkgmap.org.uk/download/mkgmap.html>
  (pakeras upp var som helst; peka på `mkgmap.jar` eller dess mapp)

## Användning

1. Installera: kopiera mappen `garmin_export` till QGIS plugin-katalog
   (`Inställningar → Användarprofiler → Öppna aktiv profilmapp` → `python/plugins`),
   starta om QGIS och aktivera *Garmin Export* i plugin-hanteraren.
2. Meny **Tillägg → Export to Garmin**.
3. Bocka för lager och välj för varje:
   * **Garmin type** – fast typkod (hex), t.ex. `0x16` = stig, `0x50` = skog.
     Egna koder kan skrivas in direkt.
   * **Type field** – valfritt fält med typkod per objekt. Samma konvention som
     tutorialen: fältet `MP_TYPE` med värden som `0x16`. Fältet har företräde.
   * **Label field** – fält som blir objektets namn på kartan.
   * **Zoom** – högsta kartnivå objektet visas på (0 = bara helt inzoomat,
     3 = syns långt utzoomat).
4. Ange kartnamn, **Family ID** (undvik 326x/327x som Garmin själva använder),
   rutstorlek (tutorialens 1° × 0,5°; 0 = ingen indelning) och utdatamapp.
5. **Export**. `.mp`-filerna hamnar i `<utdata>/mp`, kartan i `<utdata>/img`.

Kopiera sedan `img/gmapsupp.img` till mappen `Garmin` på enheten (eller dess
SD-kort). Heter filen något annat än `gmapsupp.img` visas den inte.

## Typkoder

Alla koder är **hexadecimala**; `16` och `0x16` betyder samma sak. Listorna i
dialogen är klassiska Garmin-koder (se cGPSmapper-manualens typtabeller).
Koder över `0xff` för linjer/polygoner är utökade typer och kräver en TYP-fil
för att ritas rätt (ange den i dialogen).

Höjdkurvor: använd `0x20`/`0x21`/`0x22` med höjden i etikettfältet.

## Begränsningar

* Koordinater reprojiceras alltid till WGS84.
* Inga routing-/adresssökdata skapas utöver mkgmaps `--index` (namnsökning).
* Polygonhål skrivs som flera `Data0=`-rader (cGPSmapper-konventionen).
* Max 400 rutor per export – öka rutstorleken vid större områden.

## Test

Kärnan (`core/`) är fristående från QGIS:

```
python3 -m unittest garmin_export.tests.test_core
GARMIN_MKGMAP_JAR=/sökväg/mkgmap.jar python3 -m unittest garmin_export.tests.test_core
```

Den senare kompilerar på riktigt med mkgmap.
