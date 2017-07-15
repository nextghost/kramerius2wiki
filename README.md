# Nástroje pro import knih ze systému Kramerius na WikiZdroje

Zde najdete sadu skriptů pro snadný import kompletních knih ze sbírky [Národní knihovny](http://kramerius.nkp.cz) na [WikiZdroje](https://cs.wikisource.org).

## get\_djvu.py

Tento skript stáhne a sloučí jednotlivé naskenované stránky ve formátu DjVu do jednoho velkého DjVu dokumentu. Navíc pak zkonvertuje metadata knihy do Wikišablony [Book](https://commons.wikimedia.org/wiki/Template:Book). Pokud jsou stránky naskenované v jiném formátu, například JPEG, skript nebude nic dělat.

**Parametry:** Cesta nebo URL k METS dokumentu knihy.

Můžete zadat libovolný počet METS dokumentů, skript pak bude stahovat jednotlivé knihy postupně. Wikišablona s metadaty se vypisuje po zpracování celé příslušné knihy. Výstupní DjVu soubor se ukládá do aktuálního adresáře pod stejným názvem jako METS dokument, ale s příponou `.djvu`.

### Příklad:

    $ get_djvu.py 'http://kramerius.nkp.cz/kramerius/mets/ABA001/21422766'
    21422766.djvu
    {{Book
     |Author = Jirásek, Alois
     |Title = Vojnarka
     |Subtitle = drama o 4 jednáních
     |Publisher = J. Otto
     |Date = 1891
     |City = V Praze
     |Language = cs
     |Source = {{Kramerius link|ABA001|21422766}}
     |Permission = {{PD-old}}
     |Image page = 1
     |Wikisource = :s:cs:Index:{{PAGENAME}}
    }}


### Závislosti:

- djvm (Externí program z balíku [DjVuLibre](http://djvu.sourceforge.net/) pro manipulaci s DjVu soubory.)
- Python 3
  - requests
  - lxml
