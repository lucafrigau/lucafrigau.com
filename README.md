# Sito personale di Luca Frigau

Sito web accademico e professionale di Luca Frigau, professore associato di
Statistica all'Università degli Studi di Cagliari. È un sito statico generato
con [Quarto](https://quarto.org), pensato per essere pubblicato gratuitamente su
GitHub Pages e aggiornato modificando pochi file di testo.

- Lingua del sito: inglese. Lingua di questa guida: italiano.
- Nessun database, nessun servizio a pagamento, nessun cookie o tracciamento.
- La compilazione richiede soltanto Quarto: non servono R né Python. Python
  serve solo per i test, le verifiche e per ridisegnare le mappe (citazioni,
  attività internazionali, Contact).

## Indice

1. [Installazione](#installazione)
2. [Vedere il sito in locale](#vedere-il-sito-in-locale)
3. [Struttura del progetto](#struttura-del-progetto)
4. [Operazioni ordinarie](#operazioni-ordinarie)
5. [Test e verifiche](#test-e-verifiche)
6. [Pubblicazione su GitHub Pages](#pubblicazione-su-github-pages)
7. [Dominio personale](#dominio-personale)
8. [Manutenzione periodica](#manutenzione-periodica)
9. [Componenti delle pagine (shortcode)](#componenti-delle-pagine-shortcode)

## Installazione

Strumenti necessari:

| Strumento | Uso | Installazione |
|---|---|---|
| Quarto ≥ 1.9 (testato con 1.9.37 e 1.9.36) | compila il sito | <https://quarto.org/docs/get-started/>, oppure la copia inclusa in RStudio (vedi sotto) |
| Git | versionamento e pubblicazione | già presente su macOS (`git --version`) |

Strumenti facoltativi, per le verifiche descritte più avanti:

| Strumento | Uso |
|---|---|
| Python 3 (3.9 o successivo) con PyYAML (`pip install pyyaml`) | test (`tests/run_tests.py`), mappe |
| Python 3 | controllo dei link, mappa delle citazioni, server locale |
| Google Chrome o Chromium | screenshot di revisione, controlli di accessibilità e della mappa interattiva |

RStudio e Positron aprono e visualizzano progetti Quarto, ma non sono necessari.

## Vedere il sito in locale

Dalla cartella del progetto:

```bash
quarto preview
```

Quarto compila il sito, apre il browser e lo aggiorna automaticamente a ogni
modifica dei file. Se il comando `quarto` non c'è ma è installato RStudio, si
può usare la copia di Quarto inclusa in RStudio:

```bash
/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto preview
```

In alternativa, per compilare tutto una volta:

```bash
quarto render
```

Il risultato è nella cartella `_site/` (non va modificata a mano: viene
ricreata a ogni compilazione). Per servirla con un server locale:

```bash
python3 -m http.server 4321 --bind 127.0.0.1 --directory _site
```

e aprire <http://127.0.0.1:4321>.

**Cartelle sincronizzate.** Se il progetto sta in una cartella sincronizzata
con iCloud Drive (come Documenti) o servizi simili, durante la compilazione
possono comparire copie con un numero nel nome, come `publications 2.html` o
`site_libs 2`. Vanno cancellate; i test le segnalano. Conviene tenere il
progetto in una cartella non sincronizzata (per esempio `~/Progetti`): la
cronologia è già conservata da Git. La compilazione su GitHub non ne è
toccata.

## Struttura del progetto

```
_quarto.yml               configurazione centrale: navigazione, dati personali, tema, SEO
index.qmd                 Home
about.qmd                 About
research.qmd              Research (metodi e ambiti, filoni, altre linee di ricerca, progetti finanziati)
research/                 una pagina per ciascun filone di ricerca ("research story")
publications.qmd          Publications (con la timeline e la mappa delle citazioni)
_citation-map.md          mappa delle citazioni, generata da scripts/citation_map.py
_contact-map.md           mappa della pagina Contact, generata da scripts/contact_map.py
_travel-map.md            mappa, pannelli dei marcatori ed elenco delle attività internazionali (About), generati da scripts/travel_map.py
software.qmd              Software & Apps
teaching.qmd              Teaching
contact.qmd               Contact
news.qmd                  News (elenco completo; le ultime quattro sono in Home)
404.qmd                   pagina "non trovata"
data/
  publications.bib        pubblicazioni (BibTeX), unica fonte per tutto il sito
  research.yml            filoni e aree di ricerca (schede, timeline)
  applications.yml        ambiti di applicazione dei filoni (diagramma della pagina Research)
  news.yml                notizie datate (Home e pagina News)
  software.yml            software, repository e applicazioni Shiny
  academic_travel.yml     visiting e presentazioni a convegni (mappa della pagina About)
assets/
  scss/theme.scss         colori, caratteri e stile di tutti i componenti
  scss/dark.scss          colori del tema scuro
  fonts/                  caratteri Source Serif 4 e Source Sans 3 (licenza OFL)
  img/                    favicon, marchio, grafico della Home, logo SmartLab, immagine per i social
  img/stories/            illustrazioni dei filoni (SVG generati da scripts/make_figures.py)
  html/                   piccoli frammenti HTML inclusi in ogni pagina
  js/travel-map.js        pannelli dei marcatori della mappa delle attività internazionali (About)
_extensions/site/         componenti Lua che generano elenchi, schede e grafici dai file dati;
                          links.lua apre in una nuova scheda i link verso altri siti;
                          contents.lua scrive "Explore this story" nelle Research Stories
scripts/
  make_figures.py         disegna le illustrazioni dei filoni (dati simulati, riproducibili)
  citation_map.py         aggiorna la mappa delle citazioni
  travel_map.py           disegna la mappa delle attività internazionali (About)
  contact_map.py          disegna la mappa della pagina Contact (dati OpenStreetMap)
  check_links.py          controllo dei link interni ed esterni
  audit_a11y.py           controlli automatici di accessibilità in Chrome
  check_travel_map.py     prova i pannelli della mappa (About) in Chrome: mouse, tastiera, tocchi
  screenshots.py          screenshot a pagina intera (desktop e mobile, tema chiaro o scuro)
tests/
  run_tests.py            test dei componenti e controlli di coerenza dei dati
  fixture/                piccolo progetto Quarto di prova, con dati di esempio
.github/workflows/
  publish.yml             test e compilazione a ogni push; pubblicazione manuale
robots.txt                indicazioni per i motori di ricerca
```

La cartella `review/` (documenti e screenshot per la revisione) resta solo in
locale: è esclusa da Git e non va pubblicata.

## Operazioni ordinarie

### Aggiungere una pubblicazione

Tutte le pubblicazioni sono in `data/publications.bib`. Le pagine Publications,
Home e Research, compresa la timeline, si aggiornano da sole alla compilazione
successiva.

1. Copiare la voce BibTeX (da Scopus, Google Scholar, dal sito dell'editore o
   da `https://doi.org/<DOI>` con il pulsante "Cite") nella sezione giusta del
   file. Le voci sono raggruppate per tipo:
   - `@article` → *Journal articles*
   - `@incollection` → *Book chapters*
   - `@inproceedings` → *Conference proceedings and abstracts*
2. Dare alla voce una chiave semplice e unica, per esempio
   `frigau2027clustering`.
3. Controllare gli autori nel formato `Cognome, N. and Cognome, N.`: il nome
   `Frigau` viene evidenziato automaticamente.
4. Indicare in `keywords` la linea di ricerca (vedi sotto).
5. Compilare (`quarto preview` o `quarto render`) e lanciare i test.

Esempio:

```bibtex
@article{frigau2027clustering,
  author    = {Frigau, L. and Contu, G. and Ortu, M.},
  title     = {Title of the Article as Published},
  journal   = {Computational Statistics},
  year      = {2027},
  volume    = {42},
  number    = {3},
  pages     = {1001--1025},
  doi       = {10.1007/s00180-027-00000-0},
  keywords  = {selected, clustering}
}
```

Regole utili:

- **Ordine**: le pubblicazioni sono mostrate dalla più recente; a parità di
  anno vale l'ordine del file.
- **Titoli**: compaiono esattamente come scritti nel file (maiuscole comprese).
- **Linea di ricerca** (categoria primaria): in `keywords`, l'`id` di una
  voce di `data/research.yml` (`clustering`, `trees`, `text-mining`,
  `heaping`, `image-analysis`) colloca la pubblicazione nella riga
  corrispondente dei grafici; `other-topics` è per i lavori che non
  rientrano in nessuna linea. Ogni voce ne ha esattamente una (i test lo
  controllano). Il criterio è il metodo statistico del lavoro, non il campo
  di applicazione: un lavoro applicato va nella linea del metodo che usa.
- **Pubblicazioni selezionate**: `selected` in `keywords` le mostra nella
  sezione *Selected publications*. Conviene tenerne 5-7. Le quattro della
  Home si scelgono per chiave in `index.qmd`.
- **Riassunto in una frase**: `annote = {...}` (campo BibTeX standard) compare
  sotto la voce. Scriverlo in modo comprensibile anche a chi non è del
  settore.
- **Codice e dati**: `code = {URL}` e `data = {URL}` aggiungono i pulsanti
  *Code* e *Data*. Il pulsante *Cite* mostra la voce BibTeX senza i campi
  usati solo dal sito (per questo ogni campo va su una riga propria).
- **DOI e collegamenti**: il DOI si scrive nella forma `10.xxxx/...`
  (`doi = {...}`). Il sito lo trasforma in un collegamento a
  `https://doi.org/...`, sia nel titolo sia nella riga del DOI, in tutte le
  liste (Publications, Research, Home); riconosce anche un DOI scritto come
  URL o con il prefisso `doi:`, ma i test chiedono la forma semplice. Un DOI
  non valido non diventa un collegamento e la compilazione lo segnala. In
  mancanza del DOI si può usare `url = {...}`.
- **Titoli in italiano**: aggiungere `langid = {italian}`.
- **Pubblicazioni citate nella pagina Research**: si indicano per chiave in
  `data/research.yml` (campo `publications`).

I test (`python3 tests/run_tests.py`) segnalano chiavi doppie, tipi di voce
non previsti, parole chiave sconosciute e chiavi citate dalle pagine ma
assenti dal file.

### Aggiungere un'applicazione Shiny

Le applicazioni sono descritte in `data/software.yml`; l'applicazione vera e
propria resta sul server separato che la ospita e il sito si limita a
presentarla e collegarla.

1. Copiare il modello commentato in cima al file sotto `software:`.
2. Compilare i campi: `kind: shiny-app`, titolo, descrizione (`summary`),
   tecnologie (`tech`) e collegamenti (`links`: `app`, `repo`, `docs`,
   `paper`; per un programma da installare, `download`, per esempio la pagina
   delle release su GitHub).
3. Con `featured: true` la scheda compare anche in Home (al massimo tre schede).
4. Compilare il sito.

La sezione *Interactive applications* compare automaticamente nella pagina
Software & Apps non appena esiste almeno un'applicazione. Con
`status: draft` una voce resta nel file ma non viene pubblicata; attenzione:
se il repository è pubblico, anche le bozze sono leggibili su GitHub.

Lo stesso procedimento vale per pacchetti R (`kind: r-package`, con il link
`cran` se il pacchetto è su CRAN), codice di ricerca (`research-code`) e dati
(`dataset`).

### Aggiungere una notizia

In `data/news.yml`, aggiungere in cima una voce con `date` (anno e mese,
`AAAA-MM`) e `text` (una o due frasi, Markdown ammesso). La Home mostra le
prime quattro, la pagina News tutte. I collegamenti a pagine del sito si
scrivono dalla cartella del progetto, per esempio
`[Read the story](research/heaping.qmd)`. Meglio poche notizie significative
(articoli, progetti, inviti) che molte notizie minori; i test controllano che
le date siano in ordine.

### Filoni e aree di ricerca

`data/research.yml` contiene due tipi di voci:

- i **filoni** (*research stories*), con `question`, `short`, `story` (la
  pagina) e `image` (l'illustrazione della scheda): compaiono come schede
  illustrate in Home e in Research;
- le **altre aree**, con `description` e `keywords`: compaiono nella sezione
  *Other lines of work* della pagina Research.

Per tutte, `label` è il nome breve usato nei grafici e `publications`
elenca le chiavi BibTeX dei lavori rappresentativi (con
`{{< publications area="id" >}}`). Ogni pubblicazione appartiene a una sola
linea: l'`id` della linea nel campo `keywords` del BibTeX. L'ordine nel file è
l'ordine sul sito e nei grafici; l'ultima voce, *Other topics*, raccoglie i
lavori che non rientrano nei filoni. I progetti finanziati sono scritti
direttamente in `research.qmd`.

Il diagramma *From methods to real-world problems* della pagina Research
(`{{< applications >}}`) unisce ogni filone agli ambiti in cui i suoi metodi
sono stati applicati. Gli ambiti sono in `data/applications.yml`: ognuno ha
`id`, `label` e `publications`, le chiavi BibTeX dei lavori che applicano a
quell'ambito i metodi di un filone. Le curve si ricavano da questi elenchi
(il filone di ogni lavoro è la sua area nel BibTeX); sotto il diagramma un
elenco richiudibile mostra i lavori dietro ogni curva, con il link alla voce
nella pagina Publications. Un lavoro si elenca solo se l'applicazione è
scritta nel titolo o nella storia che lo cita; può stare in due ambiti.
L'ordine degli ambiti nel file è quello del diagramma: conviene metterli
vicino ai filoni a cui sono collegati, per ridurre gli incroci. I test
controllano che le chiavi esistano, che appartengano a un filone con storia e
che ogni filone raggiunga almeno un ambito.

### Modificare le Research Stories

Ogni pagina di `research/` racconta come si è sviluppata una linea di
ricerca: il problema di partenza, i primi approcci, le domande o i limiti che
hanno motivato i lavori successivi, gli sviluppi e le direzioni più recenti.
Filoni paralleli si raccontano come tali, in sezioni distinte. La pagina ha:

- un'intestazione (sopratitolo, domanda come titolo, breve introduzione) e il
  riquadro *At a glance*, a margine su schermi larghi;
- *Explore this story*, l'elenco delle sezioni con i loro anni: lo scrive da
  solo il filtro `_extensions/site/contents.lua` dai titoli `##` della pagina
  (esclusi *The question* e *More research stories*), quindi non va
  aggiornato a mano;
- *The question*, con l'illustrazione principale;
- una sezione per ogni fase o filone, con gli anni accanto al titolo e un id
  esplicito, per esempio
  `## Oblique trees [2025–2026]{.period} {#oblique}`;
- in fondo, `## Publications in this line {#publications}` con
  `{{< publications line="id-della-linea" >}}` (tutte le pubblicazioni della
  linea) e `## More research stories` con `{{< story-nav >}}`.

I lavori si citano dentro il testo:

- `{{< cite chiave >}}` scrive rivista e anno (*Statistical Papers*, 2021),
  con il link al DOI;
- `{{< cite chiave text="CLADAG 2023" >}}` usa il testo indicato, per esempio
  il convegno per un contributo negli atti; senza DOI il link porta alla
  voce nell'elenco in fondo alla pagina.

Regole di contenuto:

- ogni articolo su rivista della linea deve avere un posto nel testo (i test
  lo controllano); capitoli e contributi a convegno sono facoltativi;
- le affermazioni sui metodi e sui risultati vengono dagli abstract o dai
  testi degli articoli, citati accanto; i legami tra lavori successivi si
  scrivono solo se documentati (date, autori, titoli, abstract), senza
  presentare un lavoro come miglioramento di un altro se l'articolo non lo
  dice; senza conferma, si descrive solo la sequenza nel tempo;
- il racconto non nomina i coautori, per restare sulle idee: il lavoro comune
  si scrive con *we*; i coautori compaiono nel riquadro *At a glance* e
  nell'elenco delle pubblicazioni (i test controllano che i cognomi degli
  autori non compaiano nel racconto);
- nel riquadro, la voce *Co-authors* elenca tutti i coautori della linea;
  se ne elenca solo alcuni si chiama *Selected collaborators* e finisce con
  `All authors are listed [with each publication](#publications).` (i test
  confrontano i nomi con `data/publications.bib`);
- i metodi introdotti da altri si attribuiscono citando l'articolo che li ha
  introdotti, e il testo distingue i metodi sviluppati (*developed*,
  *proposed*) da quelli applicati o confrontati (*applied*, *compared*);
- le illustrazioni usano dati simulati e lo dichiarano nelle didascalie: i
  numeri reali vengono solo dagli articoli;
- un risultato quantitativo di un articolo si può mostrare con i *big
  numbers* (come nelle storie sul text mining e su PARSEG) o con
  `{{< result-bars >}}` (come per TORS), sempre con i valori dell'articolo e
  la loro fonte esatta nella didascalia (tabella, figura o abstract); mai
  stime ricalcolate.

Per aggiungere un filone:

1. aggiungere la voce in `data/research.yml` (con `story`, `image` e `label`);
2. copiare una pagina di `research/` e riscriverla come sopra;
3. per le figure, aggiungere una funzione a `scripts/make_figures.py` (poi
   `python3 scripts/make_figures.py`) oppure salvare un proprio SVG in
   `assets/img/stories/` e inserirlo con lo shortcode `story-figure`;
4. assegnare le pubblicazioni del filone con il suo `id` in `keywords`.

### Aggiornare la mappa delle citazioni

La mappa della pagina Publications mostra da dove provengono le citazioni:
le città delle istituzioni a cui erano affiliati gli autori dei lavori che
citano le pubblicazioni del sito, secondo [OpenAlex](https://openalex.org)
(dati CC0). Lo script usa solo le pubblicazioni di `data/publications.bib`
che OpenAlex riconosce dal DOI, oppure quelle confermate a mano con il campo
`openalex = {W...}` (l'identificativo del lavoro in OpenAlex); gli
abbinamenti per solo titolo sono elencati come incerti e non vengono usati.
Esclude le autocitazioni; tutti i numeri della didascalia vengono dai dati.
Per aggiornarla (serve la connessione a Internet):

```bash
python3 scripts/citation_map.py
```

Lo script riscrive `_citation-map.md` (l'unico file da versionare) e salva
in `.cache/`, cartella locale esclusa da Git, i conteggi aggregati e il
resoconto degli abbinamenti (`citation-matching.json`): per confermare un
abbinamento incerto basta aggiungere alla voce il campo `openalex` indicato
dallo script. Con `--render-only` ridisegna la mappa dai conteggi salvati,
senza collegarsi a OpenAlex. Il sito non pubblica dati delle citazioni né
offre file da scaricare; i numeri visibili nella mappa restano comunque
leggibili nel codice della pagina, come per ogni sito statico. I confini dei paesi vengono da Natural Earth (pubblico dominio).
OpenAlex copre le citazioni in modo diverso da Google Scholar e Scopus: la
mappa è indicativa, come dice la didascalia. La didascalia mostra
l'essenziale; il metodo e i suoi limiti sono nel riquadro espandibile *Data
sources and limitations*.

### Mappa delle attività internazionali (pagina About)

La sezione *International academic activities* della pagina About mostra i
luoghi dei periodi di visiting e delle presentazioni a convegni. Ogni
marcatore ha un pannello con le sue attività: si apre passando con il mouse,
con il tasto Tab (Invio o la barra spaziatrice lo tengono aperto e, premuti
di nuovo, lo chiudono; Esc lo chiude sempre) e toccando il punto su telefoni
e tablet. Sotto le mappe, un riquadro chiuso, *All visiting
positions and conference presentations*, riporta tutte le attività come
elenco. Dati, mappa, pannelli ed elenco vengono da `data/academic_travel.yml`.
Vi entrano solo le attività del CV svolte **in presenza**: periodi di visiting
e presentazioni tenute personalmente (anche in sessioni invitate). Restano
fuori gli eventi online, gli atti senza presentazione, i comitati e
l'organizzazione di sessioni.

Per aggiungere un visiting o una presentazione:

1. copiare una voce dello stesso tipo in `data/academic_travel.yml` e
   modificarla. Campi: `type` (`visit` o `talk`), `name`, città e paese in
   inglese, `year`, `dates` come nel CV, `source`; per un visiting anche
   `role` (per esempio *Visiting fellow*), `unit` (facoltativo), `host` e
   `topic` (si legge "invited by *host* to collaborate on *topic*"); per una
   presentazione `event` (nome completo), `title` (titolo della
   presentazione, come nel CV) e `invited: true` se la sessione era invitata.
   I campi facoltativi senza un dato verificato si omettono;
2. scrivere la posizione della città in `lat` e `lon`, con due decimali: per
   esempio cercando la città su
   [openstreetmap.org](https://www.openstreetmap.org), dove l'indirizzo della
   pagina termina con `#map=zoom/latitudine/longitudine`. Una città già
   presente va scritta con le stesse coordinate;
3. ridisegnare la mappa (serve PyYAML, come per i test):

   ```bash
   python3 scripts/travel_map.py
   ```

4. versionare insieme `data/academic_travel.yml` e `_travel-map.md`.

Lo script disegna una mappa del mondo e una dell'Europa ingrandita
(proiezione Equal Earth, terre da Natural Earth scaricate una volta in
`.cache/`): rombi ocra per i visiting, cerchi blu per le presentazioni. I
luoghi dello stesso tipo troppo vicini condividono un marcatore (per esempio
Napoli, Caserta e Salerno), e il pannello li elenca tutti, luogo per luogo e
anno per anno. Ogni mappa ha due serie di marcatori: una per le mappe larghe e
una, con marcatori più grandi e più raggruppati, per quelle sotto i 600 px
(telefoni); in entrambe i marcatori distano almeno 24 px, come chiede il
criterio 2.5.8 delle WCAG 2.2.

I pannelli sono gestiti da `assets/js/travel-map.js` (circa 8 KB, nessuna
libreria, nessuna richiesta ad altri siti, nessun cookie): un solo pannello
aperto alla volta, sopra o sotto il marcatore e, se non c'è spazio, accanto;
sui telefoni, dopo un tocco, la pagina scorre quanto basta per mostrarlo
intero. Solo i marcatori della serie visibile sono pulsanti raggiungibili con
Tab: lo script riconosce la serie nascosta dallo stile calcolato, perché
alcuni browser (per esempio Chromium 134) danno ancora dimensioni e focus agli
elementi SVG nascosti. Senza JavaScript i marcatori mostrano il suggerimento
del browser e l'elenco resta disponibile.

I test controllano che `_travel-map.md` corrisponda ai dati, che ogni voce
abbia i campi richiesti e compaia nei pannelli e nell'elenco, e che i
marcatori non si sovrappongano e distino almeno 24 px. Il comportamento dei
pannelli si prova in Chrome, con il sito compilato e il server locale avviato:

```bash
python3 scripts/check_travel_map.py
```

Lo script apre ogni marcatore a quattro larghezze (desktop, tablet, due
telefoni con schermo tattile), nei due temi, con il mouse, la tastiera e i
tocchi, e controlla posizione, freccia, contrasto e chiusura dei pannelli. Con
`--shots cartella` salva gli screenshot dei pannelli aperti.

### Mappa della pagina Contact

La mappa della pagina Contact è un'immagine statica disegnata da
`scripts/contact_map.py` con i dati di OpenStreetMap (strade, edifici,
giardini), scaricati una volta e conservati in `.cache/`; i visitatori non
contattano OpenStreetMap né altri servizi. Il segnaposto è l'indirizzo del
dipartimento, Via Sant'Ignazio 17, nella posizione che gli assegna
OpenStreetMap (il nodo è indicato nello script); la posizione è stata
confermata nell'ottobre 2026.
L'attribuzione "© OpenStreetMap contributors", obbligatoria, compare sotto la
mappa. Si rigenera solo se cambiano la sede o l'aspetto:

```bash
python3 scripts/contact_map.py                # nuovi dati da OpenStreetMap
python3 scripts/contact_map.py --render-only  # solo il disegno
```

### Link verso altri siti

I link verso altri siti si aprono in una nuova scheda: il filtro
`_extensions/site/links.lua` aggiunge, durante la compilazione,
`target="_blank"`, `rel="noopener noreferrer"` e un testo nascosto
"(opens in a new tab)" per i lettori di schermo, anche ai link generati dagli
shortcode e a quelli scritti in HTML. Un `rel` già presente (per esempio
`rel="me"`) viene mantenuto e completato. Non tocca i link interni, le ancore,
gli indirizzi email e i link con un `target` già indicato. I domini del sito
(`own-domains` in `_quarto.yml`) contano come interni. `check_links.py`
verifica la regola su tutte le pagine.

### Aggiornare insegnamenti, profilo e contatti

- Insegnamenti dell'anno: `teaching.qmd` (sezione *Courses in …*).
- Biografia, posizioni, servizi, SmartLab: `about.qmd`; visiting e
  presentazioni a convegni: `data/academic_travel.yml` (vedi sopra).
- Dati usati in più pagine (qualifica, email, profili accademici, collegamenti
  della Home e della pagina Contact, dati strutturati per i motori di ricerca):
  sezione `person:` di `_quarto.yml`.

### Cambiare colori e caratteri

Lo stile è in `assets/scss/theme.scss`; i colori sono definiti all'inizio del
file, con il rapporto di contrasto rispetto allo sfondo. Il tema scuro
(`assets/scss/dark.scss`) ridefinisce solo i colori. Il sito segue la
preferenza del sistema del visitatore; il pulsante nella barra di navigazione
passa da un tema all'altro e il browser ricorda la scelta (in locale, senza
cookie). Dopo ogni modifica dei colori, i controlli di accessibilità
(`scripts/audit_a11y.py`) verificano il contrasto in entrambi i temi: il testo
deve restare almeno a 4,5:1 (WCAG 2.2 AA).

## Test e verifiche

Prima di ogni pubblicazione (con `quarto preview` chiuso: l'anteprima
ricompila le pagine modificate nella stessa cartella `_site` e può
sovrascrivere una compilazione avviata a parte):

```bash
python3 tests/run_tests.py                         # test dei componenti e dei dati
quarto render
python3 scripts/check_links.py _site               # link interni (bloccante)
python3 scripts/check_links.py _site --external    # anche link esterni
```

- `tests/run_tests.py` compila il progetto di prova `tests/fixture/` (dati di
  esempio, non pubblicazioni reali) e ne controlla il risultato: ordinamento,
  pubblicazioni selezionate, autori evidenziati, collegamenti a DOI e codice,
  riassunti, riquadro *Cite*, lingua, conteggi, timeline, link in una nuova
  scheda (anche con un `rel` già presente), citazioni nel testo, *Explore
  this story*. Poi controlla la coerenza dei dati veri del sito (chiavi
  BibTeX, aree, file delle figure, articoli citati nelle Research Stories,
  mappa delle attività internazionali con pannelli, elenco e distanze dei
  marcatori, notizie, software), che il sito non includa le pagine di prova,
  che i file copiati così come sono (`resources` in `_quarto.yml`) siano
  indicati a partire dalla cartella del progetto e che non ci siano copie
  lasciate dalla sincronizzazione delle cartelle. Con `--no-render` usa
  l'ultimo rendering del progetto di prova (`tests/fixture/_output/`) e
  funziona anche senza Quarto: salta solo il controllo delle pagine del
  sito, che chiede a Quarto l'elenco delle pagine.
- `check_links.py` si ferma con un errore se `_site` manca, è vuota o non
  contiene `index.html`. I DOI sono verificati con il servizio del sistema
  DOI, che dice se un DOI esiste senza passare dagli editori. Altri siti
  (per esempio Scopus) rifiutano le richieste automatiche: lo script li
  segnala come *not verifiable*, non come errori.

Con il server locale avviato (vedi sopra):

```bash
python3 scripts/audit_a11y.py --axe percorso/di/axe.min.js   # accessibilità
python3 scripts/check_travel_map.py                          # pannelli della mappa (About)
python3 scripts/screenshots.py --out review/screenshots
python3 scripts/screenshots.py --out review/screenshots --scheme dark
```

`audit_a11y.py` apre ogni pagina in Chrome a 1280 e 320 px, nei due temi, con
zoom al 200 % e con il testo raddoppiato, e controlla contrasto (anche dei
testi nei grafici), nomi accessibili, titoli, adattamento senza scorrimento
orizzontale e senza testo tagliato (un taglio con i puntini di sospensione
conta come voluto solo se il browser li disegna davvero), dimensione dei
controlli e focus visibile con il tasto Tab. Con
`--axe` esegue anche [axe-core](https://github.com/dequelabs/axe-core), il
controllo automatico più diffuso (regole WCAG 2.0-2.2, livelli A e AA, e
buone pratiche). axe-core non è incluso nel progetto: il file `axe.min.js` si
trova nel pacchetto `axe-core` su npm, per esempio
`https://registry.npmjs.org/axe-core/-/axe-core-4.14.0.tgz` (cartella
`package/` dell'archivio; versione usata per le verifiche: 4.14.0). Senza
`--axe` lo script funziona lo stesso. Quando axe non riesce a decidere un
contrasto (testi nei grafici SVG, testi di un solo carattere, celle di una
tabella che scorre), lo script lo misura sulla pagina renderizzata: confronta
uno screenshot con il testo e uno senza, e calcola il rapporto tra il colore
del testo e lo sfondo sotto ogni lettera. La soglia (4,5:1, o 3:1 per il
testo grande) deve valere per almeno il 98% dei pixel delle lettere.

Nessuno strumento automatico sostituisce una prova con un lettore di schermo
(VoiceOver: Cmd+F5 su macOS), da fare prima della prima pubblicazione. Gli
screenshot segnalano anche errori JavaScript, risorse non caricate e
qualsiasi richiesta a server diversi da quello locale (le pagine non devono
caricare nulla da terzi).

## Pubblicazione su GitHub Pages

Il sito è nel repository pubblico
[`lucafrigau/lucafrigau.com`](https://github.com/lucafrigau/lucafrigau.com) ed
è servito da GitHub Pages all'indirizzo `https://lucafrigau.com`.

Il workflow `.github/workflows/publish.yml` esegue i test, compila il sito e
controlla i link a ogni push sul ramo `main` e a ogni pull request, **senza
pubblicare**. La pubblicazione è manuale: su GitHub, *Actions → Build and
publish → Run workflow* sul ramo `main`, oppure con GitHub CLI
`gh workflow run publish.yml`. Così nulla va online senza una decisione
esplicita.

Aggiornamenti: modificare i file, verificare in locale, poi

```bash
git add -A
git commit -m "Describe the change"
git push
```

e, quando le modifiche sono pronte per il pubblico, *Run workflow*.

**Cronologia.** Il repository pubblico parte da un solo commit, lo stato del
sito alla prima pubblicazione. La cronologia di sviluppo precedente contiene i
documenti di lavoro delle revisioni: resta solo in locale, nel ramo `history`,
e non va inviata a GitHub (non usare `git push --all`).

## Dominio personale

- **`lucafrigau.com`** è l'indirizzo del sito (*Settings → Pages → Custom
  domain* del repository `lucafrigau.com`). GitHub manda da solo
  `www.lucafrigau.com` a `lucafrigau.com`.
- **`lucafrigau.it`** e `www.lucafrigau.it` portano alla stessa pagina di
  `lucafrigau.com` (per esempio `lucafrigau.it/about.html` →
  `lucafrigau.com/about.html`). GitHub Pages serve un solo dominio per sito,
  quindi il `.it` ha un piccolo repository a parte,
  [`lucafrigau/lucafrigau.it`](https://github.com/lucafrigau/lucafrigau.it),
  con la sola pagina che rimanda.
- Il sito non usa il repository `lucafrigau.github.io`: con un dominio su quel
  repository, anche gli altri siti GitHub Pages dell'account passerebbero
  sotto `lucafrigau.com`.
- **HTTPS**: i certificati li emette e li rinnova GitHub; *Enforce HTTPS* è
  attivo in *Settings → Pages* dei due repository. GitHub chiede il
  certificato quando si salva il dominio: se il DNS cambia dopo, bisogna
  togliere e rimettere il dominio in *Settings → Pages* (nel repository
  `lucafrigau.it` questo aggiunge due commit sul file `CNAME`).
- **DNS**: i due domini sono registrati presso OVH, che ne gestisce il DNS
  (*Domini → nome del dominio → Zona DNS*). Per entrambi la zona contiene:

  | Sottodominio | Tipo | Destinazione |
  |---|---|---|
  | `@` | A | `185.199.108.153` |
  | `@` | A | `185.199.109.153` |
  | `@` | A | `185.199.110.153` |
  | `@` | A | `185.199.111.153` |
  | `@` | AAAA | `2606:50c0:8000::153` |
  | `@` | AAAA | `2606:50c0:8001::153` |
  | `@` | AAAA | `2606:50c0:8002::153` |
  | `@` | AAAA | `2606:50c0:8003::153` |
  | `www` | CNAME | `lucafrigau.github.io.` |

  Nel modulo di OVH il campo *Sottodominio* è obbligatorio: `@` indica il
  dominio stesso. Gli indirizzi sono quelli della guida di GitHub "Managing
  a custom domain for your GitHub Pages site". I record della posta (MX e il
  TXT `v=spf1 …`) non riguardano il sito e restano come sono.
- **Verifica dei domini** (consigliata): nelle impostazioni dell'account
  GitHub, *Settings → Pages → Add a domain*, con un record TXT nella zona DNS.
  Così nessun altro account GitHub può usare i domini.

Se cambia l'indirizzo del sito: aggiornare `site-url`, `person.url` e
`own-domains` in `_quarto.yml`, la riga `Sitemap:` in `robots.txt`, il dominio
in *Settings → Pages* e la pagina del repository `lucafrigau.it`.

## Manutenzione periodica

Ogni tre mesi, circa un'ora:

- [ ] nuove pubblicazioni in `data/publications.bib` (con linea di ricerca e,
      se utile, riassunto in una frase); DOI e numeri di pagina delle voci
      "in press";
- [ ] una o due notizie significative in `data/news.yml`, togliendo quelle
      ormai superate dalla Home se necessario;
- [ ] mappa delle citazioni: `python3 scripts/citation_map.py`;
- [ ] nuovi visiting o presentazioni in `data/academic_travel.yml`, poi
      `python3 scripts/travel_map.py`;
- [ ] nuovi articoli su rivista citati nella Research Story della loro linea;
- [ ] a inizio anno accademico: insegnamenti in `teaching.qmd` e link al
      catalogo dei corsi;
- [ ] test, compilazione, link esterni e controlli di accessibilità (sezione
      [Test e verifiche](#test-e-verifiche)); correggere i link interrotti;
- [ ] controllo a vista di Home e Publications su telefono, in tema chiaro e
      scuro;
- [ ] una volta l'anno: versione di Quarto (aggiornarla insieme a quella
      indicata nel workflow, dopo aver ripetuto le verifiche) e versioni
      delle azioni di GitHub.

## Componenti delle pagine (shortcode)

Gli elenchi sono generati dai file dati tramite l'estensione locale
`_extensions/site/`. Si usano nelle pagine `.qmd` così:

| Shortcode | Effetto |
|---|---|
| `{{< publications type="article" >}}` | elenco per tipo (`article`, `chapter`, `proceedings`), raggruppato per anno |
| `{{< publications selected="true" >}}` | pubblicazioni con `selected` in `keywords` |
| `{{< publications keys="k1,k2" style="compact" >}}` | voci scelte, nell'ordine indicato |
| opzioni: `limit="5"`, `collapse="true"`, `summary="…"` | numero massimo; elenco richiudibile; testo del pulsante |
| `{{< pubcount type="article" >}}` | numero di pubblicazioni di un tipo |
| `{{< pub-timeline >}}` | timeline delle pubblicazioni per anno e linea di ricerca, con tabella |
| `{{< pub-lines >}}` | pubblicazioni per linea di ricerca e tipo (barre), con tabella |
| `{{< applications >}}` | filoni e ambiti di applicazione (`applications.yml`), con l'elenco dei lavori dietro ogni curva (pagina Research) |
| `{{< result-bars labels="A\|B" values="5\|3" highlight="A" caption="…" >}}` | un risultato di un articolo a barre (valori scritti nella pagina, fonte nella didascalia) |
| `{{< icon email >}}` | piccola icona decorativa prima di un titolo (`location`, `clock`, `teaching`, `university`, …); il titolo deve avere un id esplicito, per esempio `## {{< icon clock >}} Office hours {#office-hours}` |
| `{{< projects group="kind" >}}` | tutte le schede di `software.yml`, divise per tipo |
| `{{< projects featured="true" limit="3" >}}` | schede in evidenza (Home) |
| `{{< publications area="clustering" >}}` | lavori rappresentativi di un filone o di un'area (`research.yml`) |
| `{{< publications line="clustering" >}}` | tutte le pubblicazioni di una linea (`id` nel campo `keywords`) |
| `{{< cite chiave >}}` | citazione nel testo: rivista e anno, con link al DOI (`text="…"` per un testo diverso) |
| `{{< research-areas which="stories" >}}` | schede illustrate dei filoni (`which="others"` per le altre aree) |
| `{{< story-figure files="a.svg,b.svg" labels="A\|B" caption="…" >}}` | figura a pannelli SVG con etichette e didascalia |
| `{{< story-nav >}}` | collegamenti agli altri filoni (in fondo alle pagine dei filoni) |
| `{{< news limit="4" >}}` | notizie di `news.yml` (tutte se manca `limit`) |
| `{{< profile-links style="inline" >}}` | collegamenti ai profili (`style="list"`, `exclude="Email"`) |
| `{{< jsonld >}}` | dati strutturati schema.org (solo Home) |
