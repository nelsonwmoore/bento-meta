import sys
sys.path.insert(0, ".")
sys.path.insert(0, "..")
import os
from pathlib import Path
import pytest
import pytest_docker
from pdb import set_trace
from bento_meta.mdf import MDF
from bento_meta.mdb import WriteableMDB
from bento_meta.mdb.loaders import load_mdf, load_model

tdir = Path('tests/samples' if os.path.exists('tests') else 'samples')
mdfs = [str(tdir.joinpath("gdc-model.yaml")),
        str(tdir.joinpath("gdc-model-props.yaml")),]

def test_mdf_load():
    mdb = WriteableMDB()
    assert mdb
    mdf = MDF(*mdfs, handle="GDC", _commit='testcommit')
    assert mdf
    ss = load_model(mdf.model, mdb)
    Path("gdc.cypher").write_text("\n".join([str(s) for s in ss]))
    pass
