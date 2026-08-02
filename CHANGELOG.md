# Changelog

Alle wesentlichen Änderungen an USP Control werden in dieser Datei dokumentiert. Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

- Weitere Aufbereitung des vollständigen USP-Datenmodells
- Zusätzliche Modell- und FRITZ!OS-Kompatibilitätstests

## [0.9.8-beta] – 2026-08-02

### Hinzugefügt

- Gesamttraffic-Diagramm auf der USP-Control-Übersicht mit Download und Upload
- anschlussbezogenes Traffic-Diagramm in der Übersicht jedes USP-Agenten
- auswählbare Zeiträume von einer Stunde bis sieben Tagen mit beschrifteter Zeit- und Datenratenachse
- ressourcenschonende automatische Erfassung der WAN-Zähler im Fünf-Minuten-Takt

### Geändert

- Traffic wird aus echten Zählerdifferenzen als Datenrate berechnet; Zählerstände und künstlich gestreckte Kurven werden vermieden

## [0.9.7-beta] – 2026-08-02

### Hinzugefügt

- Fiber-Geräte fragen zusätzlich und ausschließlich bei erkanntem Glasfaserzugang den USP-Bereich `Device.XPON.` ab
- neue aufbereitete Anschlussbox „PON & Gegenstelle“ für OLT-Kennung und -Version, PON-ID, PON-Modus, ONU-Aktivierung, FEC, GEM-Ports und OMCI-Zuordnung
- nicht gemeldete XPON-Werte werden vollständig ausgeblendet und nicht erneut als Rohdaten dargestellt

## [0.9.6-beta] – 2026-08-02

### Geändert

- Geschwindigkeitswerte werden einheitenabhängig automatisch als bit/s, kbit/s, Mbit/s oder Gbit/s skaliert
- einheitliche SI-Skalierung für DSL, Fiber, Mobilfunk, Ethernet sowie WLAN- und LAN-Clientkapazitäten
- Rate-Parameter in den technischen Tabellen erhalten ebenfalls eine lesbare Einheit

## [0.9.5-beta] – 2026-08-02

### Behoben

- farbige Füllung der CPU- und Speicherbalken sitzt wieder vollständig und vertikal korrekt in ihrer Spur

## [0.9.4-beta] – 2026-08-02

### Geändert

- Provider-Fallback über die öffentliche WAN-IP und RIPEstat ergänzt
- ASN- und Providerabfragen werden serverseitig für 24 Stunden zwischengespeichert
- private, lokale und CGNAT-Adressen werden nicht an RIPEstat übermittelt

## [0.9.3-beta] – 2026-08-02

### Geändert

- „Letzte Nachricht“ aus dem Gerätekopf entfernt
- symmetrischer Gerätekopf mit Uptime, WAN-IP und Netz beziehungsweise echtem Providerwert
- CPU und Speicherauslastung rechts in einer gemeinsamen Ressourcenbox untereinander angeordnet
- CPU- und Speicherwerte verwenden identische, live aktualisierte Auslastungsbalken
- Providerwerte werden ausschließlich aus gemeldeten USP-Daten übernommen; andernfalls erscheint transparent das Zugangsmedium

## [0.9.2-beta] – 2026-08-02

### Geändert

- USP-Protokollversion aus den Kennzahlen der Geräteseite entfernt
- USP-Version als eigene, kompakte Spalte in die Agentenübersicht verschoben
- Gerätekopf nach der Reduzierung auf Uptime, CPU und letzte Nachricht neu ausgerichtet

## [0.9.1-beta] – 2026-08-02

### Geändert

- Produktname außerhalb der Anmeldung auf **USP Control** verkürzt
- Loginseite gestalterisch an ACS Control angeglichen; die Loginbeschriftung bleibt **USP Client Control**

### Behoben

- Geräte-Untermenüs zeigen zuverlässig den ausgewählten Darstellungsbereich
- ausstehende Live-Render können einen frisch gewählten Menübereich nicht mehr mit der Übersicht überschreiben
- fortlaufende USP-Meldungen verhindern Aktualisierungen nicht mehr durch ständig zurückgesetzte Timer
- die Agentenliste übernimmt Online- und Kontaktänderungen automatisch
- Live-Aktualisierungen bleiben auf den Gerätebereich begrenzt und laden nicht die gesamte Seite neu

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
