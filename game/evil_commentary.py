from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


FREQUENCIES = ("off", "rare", "normal", "frequent")
EXPRESSIONS = ("selbstgefällig", "gelangweilt", "schadenfroh", "begeistert", "gereizt", "panisch", "geschäftlich optimistisch")


@dataclass(frozen=True)
class Dialogue:
    id: str
    event: str
    text: str
    priority: int = 40
    weight: int = 1
    cooldown: float = 4.0
    moods: Tuple[str, ...] = EXPRESSIONS
    requires: Tuple[str, ...] = ()


def _entries(
    event: str,
    texts: Sequence[str],
    *,
    priority: int = 40,
    cooldown: float = 4.0,
    expression: str = "selbstgefällig",
    requires: Tuple[str, ...] = (),
) -> Tuple[Dialogue, ...]:
    return tuple(
        Dialogue(
            id=f"{event}_{index:02d}",
            event=event,
            text=text,
            priority=priority,
            cooldown=cooldown,
            moods=(expression,),
            requires=requires,
        )
        for index, text in enumerate(texts, 1)
    )


# Central archive. The UI contains no commentary text; all variants live here.
DIALOGUES: Dict[str, Tuple[Dialogue, ...]] = {
    "game_start": _entries("game_start", (
        "Sie sind also unser neuer Geschäftsführer? Die Messlatte liegt niedrig. Der Vorgänger liegt darunter.",
        "Willkommen zurück. Die Versicherung hat übrigens gekündigt.",
        "Während Ihrer Abwesenheit haben wir nach einem kompetenteren Nachfolger gesucht. Der Markt ist erschreckend leer.",
        "Die Basis gehört Ihnen. Die Verantwortung selbstverständlich auch. Ich habe das schriftlich.",
        "Ausgezeichnet, Sie sind da! Wir hatten bereits begonnen, nach einem kompetenten Ersatz zu suchen.",
        "Ihre Personalakte ist beeindruckend. Hauptsächlich wegen ihres Umfangs.",
        "Ein neuer Tag, eine neue Gelegenheit, Entscheidungen zu treffen, die unsere Rechtsabteilung später bereuen wird.",
        "Die Sicherheitsstandards wurden gesenkt. Aus Kostengründen. Sie verstehen.",
    ), priority=65, cooldown=1.0, expression="geschäftlich optimistisch")
    , "tower_built": _entries("tower_built", (
        "Eine weitere abschreibungsfähige Investition. Vergessen Sie nicht, die Zerstörung steuerlich geltend zu machen.",
        "Sehr schön. Noch ein Turm, den wir als Betriebsausgabe geltend machen können.",
        "Die Buchhaltung fragt, ob wir die Munition als Verbrauchsmaterial oder Mitarbeiterförderung deklarieren sollen.",
        "Militärische Aufrüstung? Nein, nein. Das sind Maßnahmen zur nachhaltigen Standortentwicklung.",
        "Architektonisch fragwürdig. Ballistisch überzeugend.",
        "Baugenehmigung? Ich dachte, wir hätten die Behörden abgeschafft.",
        "Eine weitere Investition. Das senkt die Steuerlast. Die Überlebensrate ist zweitrangig.",
        "Ein glänzender Vermögenswert. Er schießt sogar auf unsere Wettbewerber.",
    ), cooldown=5.0)
    , "tower_sold": _entries("tower_sold", (
        "Ein hervorragendes Beispiel für Personalabbau ohne lästige Kündigungsgespräche.",
        "Personalabbau abgeschlossen. Die Abfindung wurde in Munition investiert.",
        "Ein trauriger Tag für den Turm. Ein hervorragender Tag für die Bilanz.",
        "Wir nennen es nicht Rückzug. Wir optimieren unsere räumliche Präsenz.",
        "Der Turm hat das Unternehmen auf eigenen Wunsch verlassen. Sagt die Presseabteilung.",
        "Personalabbau erfolgreich. Die Betroffenen wurden nicht informiert.",
    ), cooldown=5.0)
    , "last_tower_sold": _entries("last_tower_sold", (
        "Eine mutige Entscheidung. Ich habe vorsorglich die Geschäftsführung aus Ihrer Lebensversicherung streichen lassen.",
        "Die letzte Verteidigungsanlage ist weg. Endlich ist das Budget wirklich transparent.",
        "Alle Türme verkauft. Ein sehr klares Signal an die Konkurrenz: Wir glauben an den freien Markt.",
        "Der letzte Turm ist gegangen. Die Bilanz applaudiert, die Basis schweigt.",
        "Keine Türme mehr. Das nennt man bei uns radikale Kostenoptimierung.",
    ), priority=72, cooldown=15.0, expression="schadenfroh")
    , "research_completed": _entries("research_completed", (
        "Unsere Wissenschaftler haben einen Durchbruch erzielt. Die Überlebenden verlangen jetzt Schutzkleidung.",
        "Die Ethikkommission hat Bedenken angemeldet. Ich habe ihre Finanzierung eingestellt.",
        "Wissenschaft! Endlich können wir Dinge zerstören, die wir vorher nicht einmal verstanden haben.",
        "Ein wissenschaftlicher Durchbruch. Die Ethikkommission war leider gerade im Urlaub.",
        "Unsere Forscher verlangen eine Gehaltserhöhung. Ich habe ihnen stattdessen mehr Forschung angeboten.",
        "Fortschritt bedeutet, dieselben Fehler mit deutlich teurerer Technologie zu begehen.",
        "Mehr Schaden bei gleichen Kosten. Endlich Forschung mit gesellschaftlichem Mehrwert. Für uns.",
    ), cooldown=7.0, expression="begeistert")
    , "insufficient_coins": _entries("insufficient_coins", (
        "Ihre Ambitionen sind beeindruckend. Ihr Kontostand weniger.",
        "Die Finanzabteilung hat gelacht. Ich fand das unprofessionell. Und ansteckend.",
        "Geld ist nicht alles. Aber versuchen Sie mal, einen Tesla-Turm mit Optimismus zu bezahlen.",
        "Wir akzeptieren leider keine guten Absichten als Zahlungsmittel.",
        "Ihr Geschäftsmodell basiert offenbar auf Hoffnung. Wie innovativ.",
        "Die Buchhaltung empfiehlt, zunächst das Konzept Geld zu erforschen.",
    ), priority=78, cooldown=5.0, expression="gelangweilt")
    , "small_investment": _entries("small_investment", (
        "Ein vorsichtiger Investor. Wie entzückend.",
        "Das ist kein Größenwahn. Das ist Größenwahn auf Probe.",
        "Sie investieren ja gerade genug, um meine Aufmerksamkeit zu wecken.",
        "Eine überschaubare Investition. Auch Feigheit lässt sich offenbar bilanzieren.",
        "Ihre Risikobereitschaft ist beinahe so beeindruckend wie die einer Sparkasse.",
    ), cooldown=8.0)
    , "large_investment": _entries("large_investment", (
        "Ich bewundere Menschen, die ihre Existenzgrundlage für eine hübschere Zahl aufs Spiel setzen.",
        "Eine ausgezeichnete Entscheidung! Ich habe sicherheitshalber die Evakuierungspläne verkauft.",
        "Endlich jemand, der versteht: Eine Basis ist temporär. Rendite ist eine Lebenseinstellung.",
        "Unsere Verteidigungsanlagen sind unterfinanziert. Aber schauen Sie sich diese wunderschönen Zahlen an!",
        "Die Sicherheitsabteilung möchte wissen, womit sie die Creeps aufhalten soll. Ich habe ihr Ihre Jahresprognose geschickt.",
    ), cooldown=8.0, expression="begeistert")
    , "all_investment": _entries("all_investment", (
        "ALLES?! Ich glaube, wir werden ausgezeichnet miteinander auskommen.",
        "Die Schatzkammer ist leer. Dafür besitzen wir jetzt eine sehr vielversprechende Zukunft. Theoretisch.",
        "Ein Mensch mit Visionen! Und offenbar keinerlei Selbsterhaltungstrieb.",
        "Ich habe der Sicherheitsabteilung mitgeteilt, dass sie ab sofort auf Provisionsbasis arbeitet.",
        "Die gesamte Liquidität ist weg. Dafür können wir uns die Insolvenz jetzt mit deutlich höherem Einkommen leisten.",
        "Die Finanzprognose glänzt. Der Verteidigungsetat hat dagegen bereits das Gebäude verlassen.",
    ), priority=74, cooldown=12.0, expression="begeistert")
    , "income_increased": _entries("income_increased", (
        "Geld arbeitet nicht. Geld lässt arbeiten.",
        "Unsere Einnahmen steigen. Das Geschrei draußen ist vermutlich Applaus.",
        "Wachstum! Ich liebe dieses Wort. Besonders wenn niemand fragt, woher es kommt.",
        "Die Basis brennt, aber schauen Sie sich diese Wachstumszahlen an!",
        "Unsere Quartalszahlen kennen keine Angst. Die Mitarbeiter leider schon.",
    ), cooldown=10.0, expression="geschäftlich optimistisch")
    , "first_wave": _entries("first_wave", (
        "Die Kundschaft trifft ein. Bitte begrüßen Sie sie mit angemessener Feuerkraft.",
        "Unsere ersten Kunden sind da. Ich hoffe, Sie haben keine Rückgabegarantie versprochen.",
        "Die Konkurrenz nähert sich. Zeit für eine feindliche Marktbereinigung.",
        "Der erste Termin beginnt. Bitte halten Sie die Feuerkraft griffbereit.",
        "Die Eröffnungswelle ist da. Ein hervorragender Moment für operative Kompetenz.",
    ), priority=68, cooldown=4.0)
    , "no_defense": _entries("no_defense", (
        "Die erste Welle beginnt ohne Verteidigung. Ein mutiger Ansatz, wenn auch kein besonders langer.",
        "Keine Türme vor der Welle. Ich bewundere Ihre Hingabe an empirische Forschung.",
        "Die Sicherheitsabteilung meldet: Es gibt keine Sicherheitsabteilung.",
        "Die erste Welle und kein einziger Turm. Ich nenne das ambitionierte Kostenkontrolle.",
        "Unsere Verteidigung ist derzeit ein philosophisches Konzept.",
    ), priority=82, cooldown=12.0, expression="gereizt")
    , "wave_survived": _entries("wave_survived", (
        "Die Geschäftsführung gratuliert. Weiterarbeiten!",
        "Die Konkurrenz wurde erfolgreich vom Markt entfernt.",
        "Ausgezeichnet. Die Überlebenden dürfen ihre Pause jetzt schriftlich beantragen.",
        "Noch eine erfolgreiche Runde. Ich werde den Bonus selbstverständlich persönlich entgegennehmen.",
        "Die Runde ist abgeschlossen. Der Erfolg wird umgehend meinem Vorstand zugerechnet.",
    ), priority=62, cooldown=8.0, expression="selbstgefällig")
    , "fast_enemies": _entries("fast_enemies", (
        "Unsere Gäste haben es eilig. Wie unhöflich, ohne Termin zu erscheinen.",
        "Die Konkurrenz hat offenbar ihre Lieferzeiten optimiert. Widerlich.",
        "Ich hoffe, unsere Verteidigung ist schneller als unsere Buchhaltung.",
        "Schnelle Gegner. Wenigstens respektieren sie unsere Zeitpläne.",
        "Die Konkurrenz hat Expressversand entdeckt. Kündigen Sie die Kaffeepause.",
    ), cooldown=12.0)
    , "flying_enemies": _entries("flying_enemies", (
        "Die Creeps haben die Luftfahrt entdeckt. Wer hat denen eine Lizenz ausgestellt?",
        "Das Luftverkehrsamt wurde informiert. Es hat sich vorsorglich ergeben.",
        "Unsere Grundstücksmauern zeigen unerwartete Schwächen gegenüber dem Konzept Höhe.",
        "Fliegende Konkurrenz. Unsere Bauabteilung hatte Höhe offenbar als optional markiert.",
        "Die Creeps umgehen unsere Grundstücksgrenzen. Sehr effizient, leider.",
    ), cooldown=12.0)
    , "healer_enemies": _entries("healer_enemies", (
        "Die Gegenseite bietet jetzt offenbar betriebliche Krankenversicherung an.",
        "Heiler? Unsere Konkurrenz investiert also tatsächlich in Mitarbeiterbindung.",
        "Unsere eigenen Beschäftigten verlangen jetzt auch medizinische Versorgung. Eine beunruhigende Entwicklung.",
        "Die feindliche Personalabteilung genehmigt offenbar Krankenstand.",
        "Heilung auf dem Schlachtfeld. Unsere Personalpolitik wird nervös.",
    ), cooldown=12.0)
    , "shield_enemies": _entries("shield_enemies", (
        "Die Konkurrenz investiert in Arbeitsschutz. Widerlich.",
        "Schilde. Wie ausgesprochen defensiv von ihnen.",
        "Der Gegner hat Schutzmaßnahmen. Unsere Rechtsabteilung bezeichnet das als Wettbewerbsverzerrung.",
        "Schutzschilde. Die Konkurrenz liest tatsächlich die Sicherheitsrichtlinien.",
        "Ein Schildgenerator. Wie unerfreulich verantwortungsbewusst.",
    ), cooldown=12.0)
    , "boss_appeared": _entries("boss_appeared", (
        "Der neue Bewerber für Ihre Position ist eingetroffen. Er wirkt erstaunlich qualifiziert.",
        "Ein unangekündigter Großkunde. Ich hasse Großkunden.",
        "Der feindliche Vorstand möchte offenbar persönlich verhandeln.",
        "Ich habe seine Bewerbung gesehen. Er verlangt weniger Gehalt als Sie.",
        "Ein Boss. Wunderbar. Jetzt haben unsere Probleme endlich eine angemessene Größe.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_10": _entries("boss_wave_10", (
        "Die Geschäftsführung präsentiert Ihnen unser neuestes Modell. Beschwerden werden grundsätzlich ignoriert.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_20": _entries("boss_wave_20", (
        "Der Crystal Juggernaut kommt ohne Gewährleistung. Für Sie leider auch ohne Rückgaberecht.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_30": _entries("boss_wave_30", (
        "Unser Razorwing hat die Luftfahrtabteilung übernommen. Die Landebahn war ohnehin überbewertet.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_40": _entries("boss_wave_40", (
        "Der Repair Archon repariert sich selbst. Die Buchhaltung nennt das eine bedauerlich langlebige Investition.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_50": _entries("boss_wave_50", (
        "Die Entwicklungsabteilung nennt ihn unzerstörbar. Ich bevorzuge den Begriff kosteneffizient.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_60": _entries("boss_wave_60", (
        "Der Siege Behemoth hat eine Kündigung für Ihre Basis vorbereitet. Bitte widersprechen Sie mit Feuerkraft.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_70": _entries("boss_wave_70", (
        "Inferno Reaper. Die Brandschutzversicherung hat soeben ihre Geschäftszeiten beendet.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_80": _entries("boss_wave_80", (
        "Der Void Executioner bevorzugt kurze Meetings. Seine Agenda enthält nur einen Punkt: Sie.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_90": _entries("boss_wave_90", (
        "Storm Dominator meldet sich zur Übernahme. Ich hoffe, Ihre Blitzableiter sind steuerlich absetzbar.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_wave_100": _entries("boss_wave_100", (
        "Sie wollten doch eine Herausforderung. Ich habe lediglich die Liefermenge angepasst.",
    ), priority=88, cooldown=6.0, expression="gereizt")
    , "boss_defeated": _entries("boss_defeated", (
        "Die feindliche Geschäftsführung wurde erfolgreich restrukturiert.",
        "Ausgezeichnet. Seine Abfindung beträgt null Coins.",
        "Ein erfolgreicher Führungswechsel. So stelle ich mir effiziente Personalpolitik vor.",
        "Der Großkunde wurde geschlossen. Ich erwarte eine positive Pressemitteilung.",
        "Boss entfernt. Die Konkurrenz hat jetzt eine offene Stelle und keine Hoffnung.",
    ), priority=82, cooldown=8.0, expression="schadenfroh")
    , "enemy_breakthrough": _entries("enemy_breakthrough", (
        "Unsere Verteidigung weist gewisse strukturelle Schwächen auf. Die verantwortliche Führungskraft sitzt übrigens vor dem Bildschirm.",
        "Ein kleiner Zwischenfall. Ich habe die Schadenszahlen bereits entsprechend interpretiert.",
        "Die Creeps sind eingedrungen. Vielleicht finden sie ja heraus, wer hier eigentlich zuständig ist.",
        "Interessant. Offenbar war die Mauer hauptsächlich dekorativ.",
        "Die Basis verliert Leben. Ich habe die Anzeige vorsorglich etwas kleiner gemacht.",
    ), priority=90, cooldown=3.0, expression="gereizt")
    , "last_life": _entries("last_life", (
        "Ich habe Ihre Kündigung vorbereitet. Das Datum lasse ich vorerst offen.",
        "Ich habe die Unternehmensarchive verbrannt. Sicher ist sicher.",
        "Die Lage ist stabil. Zumindest bewegt sich unser Kontostand noch.",
        "Die gute Nachricht: Unsere laufenden Betriebskosten werden vermutlich bald drastisch sinken.",
        "Rein hypothetisch, wie stehen Sie zu einem schnellen Umzug?",
        "Ich habe bereits eine Nachfolgegesellschaft gegründet. Reine Vorsichtsmaßnahme.",
    ), priority=96, cooldown=6.0, expression="panisch")
    , "game_over": _entries("game_over", (
        "Wir haben bereits einen kompetenteren Nachfolger gefunden. Er hat sogar einen Puls.",
        "Das Unternehmen ist vernichtet. Immerhin müssen wir jetzt keine Gehälter mehr zahlen.",
        "Ich möchte ausdrücklich festhalten, dass sämtliche Entscheidungen unter Ihrer Führung getroffen wurden. Meine Unterschrift ist verschwunden.",
        "Ihre Strategie war revolutionär. Noch nie wurde ein Unternehmen derart effizient liquidiert.",
        "Wir nennen das keine Niederlage. Wir nennen das eine ungeplante Standortschließung.",
        "Ihre Strategie war bahnbrechend. Bedauerlicherweise hauptsächlich für den Gegner.",
        "Die Aktionäre sind unzufrieden. Die Creeps hingegen vergeben fünf Sterne.",
        "Ich habe einen ausführlichen Bericht vorbereitet. Er besteht aus dem Wort 'Ups'.",
        "Keine Sorge. Ich habe Ihre Fehler selbstverständlich unter meinem Namen veröffentlicht. Als Satire.",
        "Das Unternehmen ist insolvent. Aber wir haben noch genügend Geld für ein beeindruckendes Abschiedsbuffet.",
        "Ich wusste, dass das passieren würde. Leider erst seit ungefähr drei Sekunden.",
        "Wir sollten das nächste Mal vielleicht VOR der Investition Türme bauen. Nur ein Gedanke.",
        "Ein historischer Moment. Die erste feindliche Übernahme ohne Beteiligung unserer Rechtsanwälte.",
        "Wir haben Ihre Erfolgsbilanz geprüft. Die gute Nachricht: Ein negativer Rekord ist technisch gesehen auch ein Rekord.",
        "Ich trete hiermit von sämtlichen Führungspositionen zurück. Herzlichen Glückwunsch.",
    ), priority=100, cooldown=0.0, expression="panisch")
    , "game_over_after_all_in": _entries("game_over_after_all_in", (
        "Ihre Renditeprognose war ausgezeichnet. Schade, dass Ihre Lebenserwartung einen kürzeren Anlagehorizont hatte.",
        "Erinnern Sie sich an Ihre brillante Investitionsstrategie? Die Creeps offenbar auch.",
        "Ihre Finanzprognose war makellos. Wir haben sie eingerahmt. Sie hängt jetzt in den Ruinen.",
    ), priority=100, cooldown=0.0, expression="panisch", requires=("all_in",))
    , "three_losses": _entries("three_losses", (
        "Wir haben Ihre Erfolgsbilanz geprüft. Die gute Nachricht: Ein negativer Rekord ist technisch gesehen auch ein Rekord.",
        "Drei Standortschließungen in Folge. Unsere Nachfolgegesellschaft ist bereits profitabel.",
        "Die Konkurrenz nennt es eine Serie. Ich nenne es konsequente Markenbildung.",
    ), priority=98, cooldown=0.0, expression="schadenfroh")
    , "corporate": _entries("corporate", (
        "Aufgrund gestiegener Nachfrage nach Überleben wurden die Preise für Verteidigungsanlagen angepasst.",
        "Die Behauptung, unsere Forschungsabteilung würde Experimente an Mitarbeitern durchführen, ist falsch. Wir führen keine Mitarbeiterlisten.",
        "90 % aller Creeps empfehlen den Verzicht auf Verteidigungsanlagen.",
        "Ihre Basis ist sicher. Diese Aussage wurde nicht unabhängig geprüft.",
        "Bitte haben Sie Geduld. Die Weltherrschaft wird vorbereitet.",
        "Bei Risiken und Nebenwirkungen fragen Sie Ihren örtlichen Artillerieturm.",
        "Unsere Mitarbeiter sind unser größtes Kapital. Deshalb haben wir sie vollständig abgeschrieben.",
        "Wir behandeln alle Spieler gleich. Gleich schlecht.",
    ), cooldown=14.0, expression="geschäftlich optimistisch")
    , "rare_speed_3": _entries("rare_speed_3", (
        "Dreifache Geschwindigkeit! So erreichen wir die Insolvenz in Rekordzeit.",
    ), priority=76, cooldown=30.0, expression="begeistert")
    , "rare_invalid_build": _entries("rare_invalid_build", (
        "Das Bauamt sagt Nein. Ich wusste nicht einmal, dass wir noch eines haben.",
    ), priority=84, cooldown=18.0, expression="gereizt")
    , "rare_blockade": _entries("rare_blockade", (
        "Wir müssen den Creeps leider einen Weg offenlassen. Irgendjemand hat offenbar ein Verkehrsrecht für Monster erfunden.",
    ), priority=84, cooldown=18.0, expression="gereizt")
    , "rare_new_record": _entries("rare_new_record", (
        "Eine bemerkenswerte Leistung. Ich werde selbstverständlich behaupten, es sei meine Idee gewesen.",
    ), priority=70, cooldown=30.0)
    , "rare_easy": _entries("rare_easy", (
        "Selbstverständlich. Wir bieten auch Führungskräften mit eingeschränktem strategischem Talent eine berufliche Perspektive.",
    ), priority=55, cooldown=30.0)
    , "rare_hard": _entries("rare_hard", (
        "Sie überschätzen sich. Ausgezeichnet. Genau diese Einstellung hat uns unsere letzten sieben Geschäftsführer gekostet.",
    ), priority=55, cooldown=30.0)
    , "restart": _entries("restart", (
        "Schon wieder Sie? Offenbar ist unser Auswahlverfahren noch immer nicht streng genug.",
        "Neuer Lauf, alte Personalakte. Die Buchhaltung ist gespannt.",
        "Ein Neustart. Sehr modern. Wir nennen es iterative Fehlentscheidung.",
    ), priority=72, cooldown=5.0, expression="gelangweilt")
    , "lan_join": _entries("lan_join", (
        "Verstärkung! Wunderbar. Jetzt haben wir jemanden, dem wir die Schuld geben können.",
        "Ein neuer Geschäftspartner. Die Haftungserklärung liegt bereits bereit.",
    ), priority=72, cooldown=8.0)
    , "lan_leave": _entries("lan_leave", (
        "Ihr Geschäftspartner hat das Unternehmen verlassen. Seine Loyalität war ohnehin steuerlich nicht absetzbar.",
        "Ein Geschäftspartner weniger. Die Verantwortungsverteilung wird dadurch erfreulich übersichtlich.",
    ), priority=72, cooldown=8.0, expression="schadenfroh")
    , "quit": _entries("quit", (
        "Sie möchten Feierabend machen? Ich finde in Ihrem Vertrag keine entsprechende Klausel.",
        "Der operative Betrieb läuft weiter. Ihre Abwesenheit wird in der Bilanz vermerkt.",
    ), priority=68, cooldown=5.0, expression="gereizt")
}


def dialogue_count() -> int:
    return sum(len(items) for items in DIALOGUES.values())


class EvilCommentary:
    """Local-only event selector; it never touches the game's random generator."""

    def __init__(self, frequency: str = "normal", animations: bool = True, text_size: str = "normal", seed: Optional[int] = None) -> None:
        self.frequency = frequency if frequency in FREQUENCIES else "normal"
        self.animations = bool(animations)
        self.text_size = text_size if text_size in {"small", "normal", "large"} else "normal"
        self.recent: Deque[str] = deque(maxlen=5)
        self.event_last_at: Dict[str, float] = {}
        self.memory: Dict[str, Any] = {"all_in": False, "sold_towers": 0, "losses": 0, "runs": 0}
        self._loss_recorded_for_run = False
        self._rng = random.Random(seed) if seed is not None else random.SystemRandom()

    def configure(self, frequency: str, animations: bool, text_size: str) -> None:
        self.frequency = frequency if frequency in FREQUENCIES else "normal"
        self.animations = bool(animations)
        self.text_size = text_size if text_size in {"small", "normal", "large"} else "normal"

    @staticmethod
    def stage(snapshot: Mapping[str, Any]) -> int:
        if snapshot.get("game_over"):
            return 5
        lives = int(snapshot.get("lives", 0))
        maximum = max(1, int(snapshot.get("max_lives", 1)))
        ratio = lives / maximum
        if ratio <= 0.20:
            return 4
        if ratio <= 0.45:
            return 3
        if ratio < 1.0:
            return 2
        return 1

    def remember(self, event: str, context: Optional[Mapping[str, Any]] = None) -> None:
        context = context or {}
        if event == "restart":
            # Keep application-wide results while making a new run unable to
            # inherit its predecessor's investment and sale decisions.
            losses = int(self.memory.get("losses", 0))
            runs = int(self.memory.get("runs", 0)) + 1
            self.memory = {"all_in": False, "sold_towers": 0, "losses": losses, "runs": runs}
            self._loss_recorded_for_run = False
            return
        if event == "all_investment" or int(context.get("percent", 0)) >= 100:
            self.memory["all_in"] = True
        if event in {"tower_sold", "last_tower_sold"}:
            self.memory["sold_towers"] = int(self.memory.get("sold_towers", 0)) + 1
        if event in {"game_over", "game_over_after_all_in"} and not self._loss_recorded_for_run:
            self.memory["losses"] = int(self.memory.get("losses", 0)) + 1
            self._loss_recorded_for_run = True

    def _allowed(self, dialogue: Dialogue, now: float, force: bool) -> bool:
        if dialogue.id in self.recent:
            return False
        if any(not self.memory.get(requirement, False) for requirement in dialogue.requires):
            return False
        last = self.event_last_at.get(dialogue.event, -float("inf"))
        if not force and now - last < dialogue.cooldown:
            return False
        if self.frequency == "off" and not force and dialogue.priority < 85:
            return False
        if self.frequency == "rare" and not force and dialogue.priority < 70 and self._rng.random() > 0.20:
            return False
        if self.frequency == "normal" and not force and dialogue.priority < 50 and self._rng.random() > 0.72:
            return False
        return True

    def trigger(
        self,
        event: str,
        snapshot: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        *,
        force: bool = False,
        now: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        now = time.monotonic() if now is None else now
        context = context or {}
        self.remember(event, context)
        candidates = [dialogue for dialogue in DIALOGUES.get(event, ()) if self._allowed(dialogue, now, force)]
        if not candidates:
            return None
        dialogue = self._rng.choice(candidates)
        self.recent.append(dialogue.id)
        self.event_last_at[event] = now
        return {
            "id": dialogue.id,
            "event": event,
            "text": dialogue.text,
            "priority": dialogue.priority,
            "expression": dialogue.moods[0] if dialogue.moods else "selbstgefällig",
            "stage": self.stage(snapshot or {}),
            "animations": self.animations,
            "text_size": self.text_size,
        }

    def has_event(self, event: str) -> bool:
        return bool(DIALOGUES.get(event))

