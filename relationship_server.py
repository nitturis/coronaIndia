from flask import Flask, request, jsonify, abort
import spacy
from spacy.tokens import Span
from spacy.tokens import Token
import functools
import re
import json
import urllib.request
import logging

nlp = spacy.load("en_core_web_lg")

logger = logging.getLogger(__name__)


def make_dict_lowercase(d):
    """
        Utliity method to convert keys and values in a dictionary `d` to lowercase.

        Args:
            `d` (:obj:`dict`): dictionary whose key and values have to be converted into lowercase
        
        Returns:
            `lower_case_dict` that is a copy of `d` but with the key and value converted to lowercase
            
    """
    lower_case_dict = dict()
    for k in d.keys():
        lower_case_dict[k.lower()] = d[k].lower()
    return lower_case_dict


def load_country_acryonym_json(
    download_url: str = "https://raw.githubusercontent.com/rohanrmallya/coronaIndia/master/data/countries_acronym_aliases_flattened.json",
) -> None:

    """
        Loading JSON that has alias / acronym to country name mapping.

        Args:
            download_url (:obj:`str`, optional): The URL from where the .json containing the alias-to-country mapping can be fetched. 

        Returns:
            json converted to :obj:`dict` if the `download_url` could be fetched and read, None otherwise.

    """

    with urllib.request.urlopen(download_url) as url:
        return json.loads(url.read().decode()) if url.getcode() == 200 else {}


country_acronym_lookup = make_dict_lowercase(load_country_acryonym_json())


def acronym_to_country(acronym):
    """
        Retrieve country name from `acronym` using `country_acronym_lookup` as reference

        Args:
            acryonym (:obj:`str`): acronym for which a country has to be searched
        
        Returns:
            str: the `country`  mapped to `acronym` if such a mapping is found.
                 the `acronym` if no mapping is found
    """
    country = country_acronym_lookup.get(acronym.lower())
    return country.title() if country != None else acronym.title()


with urllib.request.urlopen(
    "https://raw.githubusercontent.com/bhanuc/indian-list/master/state-city.json"
) as url:
    state_city = json.loads(url.read().decode())


l = ["India", "Mumbai"]
for k, v in state_city.items():
    l.append(k)
    l = l + v

l = [ele.replace("*", "") for ele in l]


def get_travel_status(span):
    if span.label_ == "GPE":
        prev_token = span.doc[span.start - 1]
        if prev_token.text in ("from", "through", "via", "Via"):
            return "from"
        elif prev_token.text in ("to", "and"):
            return "to"
        return None


def get_nat(span):
    if span.label_ == "NORP":
        return span.text


def get_rel(token):
    if token.text == "of":
        prev_token = token.doc[token.i - 1]
        prev2 = None
        if token.i > 2:
            prev2 = token.doc[token.i - 2]
            if prev2.text.lower() == "and" and str(token.doc[token.i - 3])[0] != "P":
                return f"{token.doc[token.i - 3]} {token.doc[token.i - 2]} {token.doc[token.i - 1]}"
        if prev_token.text.lower() in ("members", "member"):
            return "Family Member"
        else:
            return prev_token.text


def extract_relationship(doc):
    ids = []
    output = []
    for tok in doc:
        if tok._.relationship:
            ids.append(tok.i + 1)
    ids.append(doc.__len__())
    for i in range(len(ids) - 1):
        w = re.findall("P[0-9]+", str(doc[ids[i] : ids[i + 1]]))
        output.append({"link": doc[ids[i] - 1]._.relationship, "with": w})
    return output


def extract_travel_place(doc):
    travel = []
    for ent in doc.ents:
        if ent._.travel_status:
            travel.append(ent.text)
    return list(map(acronym_to_country, travel))


def extract_nationality(doc):
    nat = []
    for ent in doc.ents:
        if ent._.nationality:
            nat.append(ent._.nationality)
    return nat


def extract_foreign(doc):
    is_foreign = []
    for ent in doc.ents:
        if ent._.travel_status:
            is_foreign.append(
                {
                    "place": acronym_to_country(ent.text),
                    "is_foreign": not (ent.text in l),
                }
            )
    return is_foreign


Span.set_extension("travel_status", getter=get_travel_status, force=True)
Span.set_extension("nationality", getter=get_nat, force=True)
Token.set_extension("relationship", getter=get_rel, force=True)

app = Flask(__name__)

default_result = {
    "nationality": [],
    "travel": [],
    "relationship": [],
    "place_attributes": [],
}


@functools.lru_cache(30000)
def record_processor(sent):
    logger.info(f"Travel Input: {sent}")
    if not sent:
        return default_result
    s = re.sub(r"[^\w\s]", " ", sent)
    doc = nlp(s)
    return {
        "nationality": extract_nationality(doc),
        "travel": extract_travel_place(doc),
        "relationship": extract_relationship(doc),
        "place_attributes": extract_foreign(doc),
    }


def process_records(records):
    history = []
    for r in records["patients"]:
        if not ("notes" in r.keys()):
            history.append(default_result)
            logger.info(f"ಥ_ಥ Missing Notes")
        else:
            history.append({r["patientId"]: record_processor(r["notes"])})
            logger.info(
                f"Travel Output : {r['patientId']}: {record_processor(r['notes'])}"
            )
    return {"patients": history}


@app.route("/", methods=["POST"])
def single():
    try:
        req_data = request.get_json()
        results = process_records(req_data)
    except TypeError:
        logger.info(f"ಠ~ಠ TypeError Aborting")
        logger.info(f"Error Data : {req_data}")
        abort(400)
    except KeyError:
        logger.info(f"ಠ╭╮ಠ KeyError Aborting")
        logger.info(f"Error Data : {req_data}")
        return jsonify(error="Not the correct request format!")
    return results


#if __name__ == "__main__":
#    app.run()
# app.run()