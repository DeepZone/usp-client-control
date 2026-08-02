# Changelog

Alle wesentlichen Änderungen an USP Control werden in dieser Datei dokumentiert. Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

- Weitere Aufbereitung des vollständigen USP-Datenmodells
- Zusätzliche Modell- und FRITZ!OS-Kompatibilitätstests

## [0.11.5-beta] – 2026-08-02

### Geändert

- Gerätedienste und BulkData-Messdatenexport in „USP & MQTT“ integriert
- separaten Menüpunkt „Dienste“ zugunsten einer schlankeren Gerätenavigation entfernt
- USP-, MQTT- und Dienstefunktionen in einer gemeinsamen, durchsuchbaren Funktionsansicht zusammengeführt
- Abruf und dynamische Aktualisierung der Gerätedienste bleiben vollständig erhalten

## [0.11.4-beta] – 2026-08-02

### Hinzugefügt

- gezielter USP-Abruf der vollständigen Gerätedienste und des `BulkData`-Bereichs
- automatischer Erstabruf auf der Diensteseite, wenn noch keine Servicewerte vorliegen
- manueller, jederzeit wiederholbarer Abruf über „Dienste abrufen“

### Geändert

- neu eintreffende Dienstedaten werden ohne vollständiges Neuladen der Seite dynamisch dargestellt

## [0.11.3-beta] – 2026-08-02

### Hinzugefügt

- gezielter USP-Abruf der vollständigen Telefoniestruktur einschließlich Rufnummern, SIP-Netzen, DECT-Basen und Mobilteilen
- automatischer Erstabruf, wenn die Telefonieseite eines Agenten noch keine `VoiceService`-Daten enthält
- manueller, jederzeit wiederholbarer Abruf über „Telefoniedaten abrufen“

### Geändert

- leere Telefoniebereiche unterscheiden jetzt verständlich zwischen „nicht eingerichtet“ und „noch nicht vom Gerät empfangen“

## [0.11.2-beta] – 2026-08-02

### Geändert

- kompakte Kennzahlen- und Qualitätsboxen wieder mit bis zu vier Spalten dargestellt
- ausschließlich große Inhaltskarten bleiben auf maximal drei Spalten begrenzt
- große Restkarten nutzen weiterhin automatisch die vollständige Zeilenbreite

## [0.11.1-beta] – 2026-08-02

### Geändert

- Infoboxen und Bereichskarten auf maximal drei Spalten begrenzt
- einzelne Karten in einer Restzeile nutzen automatisch die gesamte verfügbare Breite
- zwei Karten in einer Restzeile teilen sich die gesamte Breite gleichmäßig

## [0.11.0-beta] – 2026-08-02

### Hinzugefügt

- eigener Gerätebereich „Telefonie & DECT“
- aufbereitete SIP-Konten mit Registrierung, Rufnummer beziehungsweise URI, Benutzer und Netzzuordnung
- SIP-Netze mit Registrar, Proxy, Outbound-Proxy, Ports und STUN-Status
- DECT-Basen mit Aktivierung, Standard, RFPI, Kapazität und Repeater-Unterstützung
- DECT-Mobilteile mit Name, Modell, Hersteller, Firmware, Basiszuordnung, IPUI und Codecs

### Geändert

- „Internet & IP“ als übersichtliche Betriebsseite mit IP-Schnittstellen, Adressen, Traffic, Fehlern, Geschwindigkeiten, PPP, DHCP und DNS neu gestaltet
- `avm-wg` wird verständlich als WireGuard-Schnittstelle gekennzeichnet
- „Dienste“ erhält eine kompakte Statusübersicht und getrennte, weiterhin bedienbare Detailgruppen
- schreibbare SIP-, DECT- und IP-Einstellungen sind rollenabhängig direkt aus den aufbereiteten Ansichten erreichbar

## [0.10.5-beta] – 2026-08-02

### Geändert

- Infoboxen und Bereichskarten verwenden abhängig von ihrer Anzahl automatisch eine bis vier Spalten
- WLAN-Radios stehen bei zwei, drei oder vier Frequenzbändern vollständig in einer gemeinsamen Reihe
- IP-, LAN- und Heimnetz-Schnittstellen einschließlich zusätzlicher `avm-wg`-Instanzen werden bis zu vier Karten je Zeile angeordnet
- Kartentypografie, Abstände und Detailwerte skalieren platzabhängig und halten zusammengehörige Angaben möglichst in einer Zeile

## [0.10.4-beta] – 2026-08-02

### Behoben

- Agenten-Trafficgrafik bleibt nicht mehr bei „Traffic-Verlauf wird geladen …“ stehen
- Live-Differenzaktualisierungen lassen bereits geladene Diagramme und deren Zeitraumwahl unverändert
- Antworten veralteter Traffic-Abfragen können keine inzwischen entfernten Vergleichselemente mehr aktualisieren

## [0.10.3-beta] – 2026-08-02

### Geändert

- Live-Werte werden per DOM-Differenz aktualisiert, ohne den sichtbaren Gerätebereich neu aufzubauen
- WebSocket-Aktualisierungen werden gebündelt und in einer freien Browserphase verarbeitet
- neue oder entfernte Prozesse, WLAN-Clients und andere Instanzen werden dynamisch in die bestehende Ansicht eingefügt
- Scrollpositionen, geöffnete Detailbereiche, Eingabewerte und bestehende Bedienelemente bleiben bei Live-Updates erhalten

## [0.10.2-beta] – 2026-08-02

### Geändert

- WLAN-Client-Heatmap vollständig entfernt
- Rohdatenabteilungen „Heimnetzgeräte · Host“, „Heimnetzgeräte · Allgemein“ und „Netzwerktopologie · AL“ von der Heimnetzseite entfernt
- zusätzliche IEEE-1905-Werte direkt in Mesh-Knoten und Clientdetails aufbereitet: Mesh-Rolle, Geräteklasse, Softwarestand, LLDP-Erkennung, Link-Verfügbarkeit, RCPI/RSSI, Kanalauslastung und letzter Topologiestand
- Host-Alias als weitere sinnvolle Quelle für die Gerätebezeichnung ergänzt
- reservierte IEEE-1905-Messwerte wie `255` werden als „nicht gemeldet“ behandelt

## [0.10.1-beta] – 2026-08-02

### Geändert

- WLAN-Seite konsequent auf Radios, Frequenzbänder, Kanäle, Sendeleistung, Auslastung, SSIDs und Sicherheit reduziert
- WLAN-Client-Heatmap und sämtliche clientspezifischen Verbindungsdetails in den Bereich „Heimnetz“ verschoben
- modellabhängige FRITZ!-Gerätesymbole für FRITZ!Box, Smart Gateway, Repeater und Powerline in der Mesh-Topologie ergänzt
- clientspezifische Access-Point-Rohwerte werden nicht mehr auf der WLAN-Seite wiederholt

## [0.10.0-beta] – 2026-08-02

### Hinzugefügt

- interaktive Mesh-Übersicht unter „Heimnetz → Netzwerktopologie“
- FRITZ!Box als Mesh Master sowie getrennte Darstellung von Mesh-Komponenten, WLAN-, LAN- und Powerline-Geräten
- Zusammenführung von IEEE-1905-Topologie, aktiven Hosts, Schnittstellen, SSIDs und AVM-Verbindungsmetriken
- Filter nach Verbindungstyp sowie anklickbare Clients mit Qualitäts-, Kapazitäts- und Zuordnungsdetails
- optische Unterscheidung zwischen sicher gemeldeten und aus Host-Schnittstellen abgeleiteten Beziehungen

### Geändert

- bereits in der Mesh-Ansicht aufbereitete Topologieparameter werden unter „Weitere Heimnetzfunktionen“ nicht erneut als Rohdaten angezeigt

## [0.9.9-beta] – 2026-08-02

### Geändert

- skalierbare Traffic-Telemetrie für große Agentenbestände: aktive Agenten werden gleichmäßig über einen 15-Minuten-Grundtakt verteilt statt gleichzeitig abgefragt
- gerade betrachtete Agenten erhalten vorübergehend eine höhere Auflösung von fünf Minuten
- Zählerdifferenzen werden sofort als kompakte Datenraten-Messpunkte verdichtet und nur acht Tage aufbewahrt
- Gesamttraffic wird serverseitig aus den verdichteten Messpunkten aggregiert; Rohzähler müssen dafür nicht mehr über die API übertragen werden
- fehlende oder veraltete Messungen werden nicht als Nullwerte interpretiert und erscheinen im Diagramm als Unterbrechung

### Behoben

- interne Traffic-Abfragen erzeugen keine Einträge mehr in der Ereignis- oder Auftragsliste

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
