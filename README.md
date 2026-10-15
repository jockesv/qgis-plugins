# qgis-plugins

Samling QGIS-plugins. Varje plugin ligger i en egen mapp som kan kopieras
direkt till QGIS plugin-katalog.

| Plugin | Beskrivning |
|---|---|
| [`garmin_export`](garmin_export/) | Exporterar vektorlager till Garmin GPS (IMG via mkgmap, eller GPX) |

## Installera

1. Ladda ner zip-filen för pluginet, t.ex.
   [`garmin_export-0.1.0.zip`](https://github.com/jockesv/qgis-plugins/raw/main/dist/garmin_export-0.1.0.zip).
2. I QGIS: **Tillägg → Hantera och installera tillägg → Installera från ZIP**,
   välj filen och klicka **Installera**.
3. Aktivera pluginet i fliken *Installerade*. Det dyker upp under **Tillägg**.

### Garmin Export: extra krav

För att skapa en Garminkarta (IMG) behövs **Java** och **`mkgmap.jar`**
från <https://www.mkgmap.org.uk/download/mkgmap.html>. Peka ut `mkgmap.jar` i
exportdialogen. GPX-export behöver inget extra.

Kopiera sedan den färdiga `gmapsupp.img` till mappen `Garmin` på enheten.
Mer information finns i [`garmin_export/README.md`](garmin_export/README.md).
