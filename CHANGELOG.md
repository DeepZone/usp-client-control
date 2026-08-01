# Changelog

Alle wesentlichen Änderungen an USP Client Control werden in dieser Datei dokumentiert. Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

- Weitere Aufbereitung des vollständigen USP-Datenmodells
- Zusätzliche Modell- und FRITZ!OS-Kompatibilitätstests

## [0.9.0-beta] – 2026-08-02

### Hinzugefügt

- neues Produktbranding als **USP Client Control** mit eigenem Logo
- NoiSens-Standardlogo und administrativer Upload eines individuellen Unternehmenslogos
- Benutzerverwaltung mit Administrator-, Operator- und Viewer-Rolle
- persönliches Nutzerprofil und Kennwortwechsel
- rollenbasierte Geräteänderungen sowie Audit-Protokoll
- medienbezogene Aufbereitung für Cable, DSL, Mobile, Fiber und Ethernet-WAN
- Live-Ansichten für Agenten-, System-, Anschluss-, LAN- und WLAN-Werte
- WLAN-Client-Heatmap und dynamische Detailansichten
- FRITZ!-ähnliche Spektrum-, Pegel-, Qualitäts- und Verlaufsgrafiken
- optionale GenieACS-Anbindung für Kundennummern

### Sicherheit

- sensible Laufzeitwerte bleiben in `.env` und persistenten Volumes
- Unternehmensbranding und Benutzerverwaltung sind Administratoren vorbehalten
- Viewer besitzen ausschließlich Leserechte

### Status

- öffentliche Beta zur technischen Erprobung; noch nicht für unbeaufsichtigten Produktivbetrieb freigegeben
