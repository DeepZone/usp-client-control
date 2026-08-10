# Changelog

Alle wesentlichen Änderungen an USP Control werden in dieser Datei dokumentiert. Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

## [1.2.4] – 2026-08-11

### Geändert

- öffentliche Dokumentation und Konfigurationsoberfläche auf den produktiv genutzten MQTT-Betrieb fokussiert
- interne Entwicklungsarbeiten werden nicht in öffentlichen Projektunterlagen beschrieben

## [1.1.2] – 2026-08-05

### Hinzugefügt

- Agenten können nach einem Wechsel des Zugangsmediums controllerseitig zurückgesetzt und vollständig neu synchronisiert werden
- Administratoren können Agenten samt Messwerten, Historie, Aufträgen, Ereignissen und Datenmodell dauerhaft löschen

### Sicherheit

- Zurücksetzen ist auf Operatoren und Administratoren, endgültiges Löschen ausschließlich auf Administratoren beschränkt
- beide Aktionen verlangen eine ausführliche Sicherheitsbestätigung; ein Reset verändert weder FRITZ!Box-Konfiguration noch USP-Zugang

### Geändert

- nach einer Datenmodellsynchronisation liest USP Control nur tatsächlich unterstützte Live-Bereiche und erkennt dadurch DSL-/Fiber-Wechsel ohne veraltete Zugangsdaten

## [1.1.1] – 2026-08-03

### Geändert

- technische Live-Profilanalyse von der Geräteübersicht entfernt; automatische Synchronisation, Subscriptions und Polling bleiben unverändert aktiv

## [1.1.0] – 2026-08-03

### Hinzugefügt

- agentenspezifische Live-Profile auf Basis des synchronisierten USP-Datenmodells
- automatische vollständige Datenmodellsynchronisation für online kommende Agenten
- automatische Subscriptions für Wertänderungen, Ereignisse, Objektanlage/-löschung und abgeschlossene Operationen
- dynamische Auflösung von `{i}`-Datenmodellpfaden auf tatsächlich vorhandene FRITZ!Box-Instanzen
- übersichtliche Live-Profilanzeige mit Fähigkeits- und Fallback-Zählern auf der Agentenseite
- konfigurierbares, ressourcenschonendes Fallback-Polling für relevante nicht abonnierbare Messwerte

### Geändert

- „Live-Updates aktivieren“ ersetzt die feste CPU-Subscription durch ein automatisch ermitteltes Geräteprofil
- neue und gelöschte USP-Objekte werden ohne vollständigen Seitenneuaufbau an die Oberfläche gemeldet
- Jobversand wird auch für interne, protokollierte Live-Aktualisierungen sicher wiederverwendet

### Behoben

- abonnierbare FRITZ!OS-Werte außerhalb von `CPUUsage` wurden zuvor nicht berücksichtigt
- doppelte persistente Subscriptions werden anhand von Typ und Referenz zuverlässig vermieden

## [1.0.1] – 2026-08-02

### Hinzugefügt

- einheitlicher „Aktualisieren“-Button auf jeder Geräteseite
- fachlich aufbereitete WAN-Fallbackansicht für Geräte ohne klassifiziertes Zugangsmedium

### Geändert

- Release-Status, sichtbare Versionsangaben und Browser-Asset-Version auf 1.0.1 aktualisiert
- technische USP-Werte bleiben intern vollständig verfügbar, erscheinen aber nur noch in zugeordneten Funktionsansichten
- USP & MQTT vollständig als Controller-, Broker-, Subscription- und Diensteübersicht aufbereitet

### Entfernt

- reine „Expertenansicht“ mit vollständigen USP-Parameterlisten aus dem Gerätemenü
- ausklappbarer USP-Komplettdump und sichtbare interne USP-Pfade aus den Clientdetails
- rohe Parameterpfad-Tabelle aus der allgemeinen WAN-Anschlussansicht
- generische Rohdatenblöcke aus System, WLAN, Internet & IP sowie USP & MQTT

## [0.15.5-beta] – 2026-08-02

### Hinzugefügt

- Roaming-Status sichtbar im Bereich „SIM und Zugang“ dargestellt
- Roaming gemäß AVM-USP-Datenmodell über `Device.Cellular.RoamingEnabled` aktivier- und deaktivierbar
- rollenabhängige Bedienung und Sicherheitsabfrage vor jedem USP-SET

## [0.15.4-beta] – 2026-08-02

### Geändert

- Bereich „Weitere Anschlussfunktionen“ vollständig aus allen Anschlussansichten entfernt
- „Unterstützte Mobilfunkbänder“ ans Ende der Mobilfunk-Anschlussseite verschoben

## [0.15.3-beta] – 2026-08-02

### Behoben

- RSSI in die serverseitige Historienerfassung aufgenommen
- RSRP, RSRQ und RSSI werden bei jeder Messabfrage auch bei unverändertem Wert als echter Messpunkt gespeichert
- aktuelle RSSI-Messung erscheint sofort im Diagramm; bis zum zweiten Messpunkt mit Kennzeichnung „noch keine Historie“

## [0.15.2-beta] – 2026-08-02

### Geändert

- RSRP, RSSI und RSRQ wieder in einem gemeinsamen Mobilfunkdiagramm im FRITZ!-Stil dargestellt
- getrennte linke und rechte Y-Achse für Empfangspegel und Signalqualität verhindert verzerrte Linienlagen
- kontrastreiche Linien in Blau, Grün und Orange mit stärkerer Abhebung vom Diagrammhintergrund
- Zeitraum wählbar zwischen 1 Stunde, 6 Stunden, 24 Stunden und 7 Tagen; Standard bleibt 24 Stunden

## [0.15.1-beta] – 2026-08-02

### Geändert

- Funkzellenrollen in der Tabelle wieder als PCC, SCC und Neighbor bezeichnet
- verbundene PCC- und SCC-Zellen deutlich grün hinterlegt
- Mobilfunk-Verlauf in getrennte Diagramme für Empfangspegel und Signalqualität aufgeteilt
- automatische Achsenreserve verhindert Linien direkt am oberen und unteren Diagrammrand
- kontrastreiche Farben für RSRP, RSSI und RSRQ ohne schwer lesbare lila Linie

## [0.15.0-beta] – 2026-08-02

### Geändert

- Menüpunkt und Seitentitel in die Mehrzahl „Interfaces“ umbenannt
- Interface-Seite um eine kompakte Gesamttabelle für Status, Zuordnung, Adressen, Datenraten, Traffic und Fehler erweitert
- aufklappbare Rohdaten vollständig von der Interface-Seite entfernt
- Datenraten automatisch in bit/s, kbit/s, Mbit/s oder Gbit/s skaliert
- vorhandene 24-Stunden-Verläufe geeigneter Interface-Messwerte direkt als ruhige Mini-Diagramme in der Tabelle dargestellt

## [0.14.2-beta] – 2026-08-02

### Geändert

- doppelten Rohdatenbereich „IP & WAN · Interface“ unter „Internet & IP“ entfernt; die aufbereitete Darstellung befindet sich im Menüpunkt „Interface“

## [0.14.1-beta] – 2026-08-02

### Behoben

- Menüpunkt „Interface“ in die tatsächlich aktive, erweiterte Gerätenavigation aufgenommen

## [0.14.0-beta] – 2026-08-02

### Hinzugefügt

- neuer Gerätemenüpunkt „Interface“ mit aufbereitetem TR-181/USP-Interface-Stack
- verständliche Zuordnung über `LowerLayers` von IP und PPP/VLAN/Link bis zum physischen Zugangsmedium
- gemeinsame Darstellung für Ethernet, WLAN, DSL, DOCSIS, Mobilfunk, Fiber, ATM und PTM
- Statusübersicht, IP- und MAC-Adressen, MTU, Datenraten, Traffic-Zähler, Fehlerzähler und VLAN-Zuordnung
- Erkennung nicht aufgelöster Interface-Verweise sowie gezielter Live-Abruf unterstützter Interface-Bereiche
- weitere gelieferte Werte bleiben je Interface kompakt aufklappbar und bedienbar

## [0.13.1-beta] – 2026-08-02

### Geändert

- eigene FRITZ!-inspirierte SVG-Gerätesymbole anhand der offiziellen Produktformen
- separate Silhouetten für FRITZ!Box, hohe und kompakte FRITZ!Repeater, FRITZ!Powerline und FRITZ!Smart Gateway
- automatische Symbolauswahl anhand des über USP gemeldeten Modellnamens
- einheitlicher weiß-roter Hardware-Look mit Status-LEDs, Gehäuseschatten und gerätespezifischen Details

### Rechtliches

- keine fremden Produktfotos oder AVM-Markengrafiken in das öffentliche Repository übernommen
- Symbole sind eigenständige, reduzierte SVG-Illustrationen ohne eingebettete FRITZ!-/AVM-Logos

## [0.13.0-beta] – 2026-08-02

### Geändert

- PHY-Rate verständlich als „Maximal möglich“ und MAC-Kapazität als „Aktuell ausgehandelt“ benannt
- absolute Geschwindigkeitsgrenzen durch eine relative Bewertung gegenüber der PHY-Obergrenze ersetzt
- PHY-Ausnutzung getrennt nach Up- und Downstream ermittelt; die schwächere Richtung bestimmt den Effizienzwert
- WLAN-Qualität kombiniert PHY-Ausnutzung, RSSI/RCPI, Link-Verfügbarkeit, Kanalauslastung und Latenz
- fehlende Einzelmetriken führen nicht mehr automatisch zu einer Abwertung; vorhandene Komponenten werden gewichtsnormiert

### Gewichtung

- 40 % aktuell ausgehandelte MAC-Kapazität relativ zum PHY-Maximum
- 25 % WLAN-Signal aus RCPI beziehungsweise RSSI
- 15 % Link-Verfügbarkeit
- 10 % Kanalauslastung
- 10 % Latenz

## [0.12.6-beta] – 2026-08-02

### Geändert

- sämtliche Clientdetails öffnen über alle Access-Medien als mittiges Popup
- einheitliche Darstellung für Cable, DSL, Fiber, Mobilfunk und Ethernet-WAN
- rechter Seiten-Drawer auch bei vollständig zugeordneten IEEE-1905-Clients entfernt

## [0.12.5-beta] – 2026-08-02

### Geändert

- Clientdetails der Cable-Box öffnen jetzt als mittig zentriertes Popup
- seitlich bildschirmfüllende Cable-Detailansicht durch einen begrenzten, scrollbar bleibenden Dialog ersetzt
- responsive Popup-Darstellung für kleinere Bildschirme

## [0.12.4-beta] – 2026-08-02

### Geändert

- FRITZ!Box selbst wird nicht mehr zusätzlich als Heimnetz-Client aufgeführt
- Mesh-Komponenten wie FRITZ!Smart Gateway, Repeater und Powerline-Geräte sind anklickbar
- Mesh-Komponenten öffnen über ihre Host-Zuordnung die einheitliche Live-Detailansicht

## [0.12.3-beta] – 2026-08-02

### Geändert

- einheitliche Heimnetz-Client-Detailansicht für Cable, DSL, Fiber und Mobilfunk
- auch Clients ohne vollständige IEEE-1905-Zuordnung öffnen die normale Live-Detailansicht
- fehlende Qualitätsmesswerte werden neutral als „Keine Messwerte“ dargestellt

### Behoben

- abweichender kompakter Dialog für einzelne Clients der Cable-Box entfernt

## [0.12.2-beta] – 2026-08-02

### Behoben

- Speedtests bleiben nach einem MQTT- oder WAN-Verbindungsabbruch nicht dauerhaft im Status „Läuft“
- verwaiste asynchrone Tests erhalten nach 90 Sekunden eine verständliche Zeitüberschreitungsdiagnose
- nach einem unterbrochenen Test kann anschließend wieder eine neue Messung gestartet werden

## [0.12.1-beta] – 2026-08-02

### Hinzugefügt

- Schaltfläche „Speedtest-Fähigkeit prüfen“ direkt auf der Speedtestseite
- gezielter Abruf von Unterstützungswert und Diagnose-Command-Schema
- automatische Aktualisierung der Fähigkeitsanzeige nach der Geräteantwort

## [0.12.0-beta] – 2026-08-02

### Hinzugefügt

- eigener Geräte-Menüpunkt „Speedtest“ für IP-Layer-Kapazitätsmessungen nach BBF TR-471
- Download- und Upload-Messungen über die asynchrone USP-Operation `Device.IP.Diagnostics.IPLayerCapacity()`
- automatisch aktualisierter Laufstatus ohne Neuladen der Geräteansicht
- Ergebnisübersicht für Kapazität, Paketverlust, Latenz und Jitter
- skaliertes Verlaufsdiagramm für gemessene Datenrate und angebotene Last
- Verlauf der letzten 25 Messungen je USP-Agent
- zentrale, ausschließlich für Administratoren sichtbare UDPST-Konfiguration
- gezielte Synchronisierung der Speedtest-Fähigkeit direkt auf der Speedtestseite

### Sicherheit

- UDPST-Authentifizierungsschlüssel werden weder an den Browser zurückgegeben noch im Audit- oder Auftragsprotokoll offengelegt

### Geändert

- asynchrone USP-Operationen bleiben bis zur `OperationComplete`-Benachrichtigung im Status „Läuft“

## [0.11.6-beta] – 2026-08-02

### Hinzugefügt

- aufbereitete FRITZ!Box-Ereignisliste aus `Device.DeviceInfo.DeviceLog` auf der Geräteübersicht
- eigener USP-Abruf über „Ereignisse aktualisieren“
- verständliche farbliche Einordnung erfolgreicher, auffälliger und fehlerhafter Ereignisse
- kompakte, scrollbar begrenzte Anzeige der neuesten 50 Einträge

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
- Live-Aktualisierungen werden gebündelt und in einer freien Browserphase verarbeitet
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
