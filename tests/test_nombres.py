from tesa.nombres import clave, normalizar_nombre, similitud


def test_normalizar_quita_tildes_particulas_y_signos():
    assert normalizar_nombre("Aída Galila", "Benítez de Rivas") == "AIDA GALILA BENITEZ RIVAS"
    assert normalizar_nombre("JOSÉ M. PÉREZ-LÓPEZ") == "JOSE PEREZ LOPEZ"
    assert normalizar_nombre(None, "nan") == ""


def test_clave_no_depende_del_orden():
    a = clave(normalizar_nombre("AIDA GALILA BENITEZ DE RIVAS"))
    b = clave(normalizar_nombre("BENITEZ DE RIVAS", "AIDA GALILA"))
    assert a == b


def test_similitud_tolera_errores_de_tipeo():
    a = clave(normalizar_nombre("JUAN CARLOS GIMENEZ ROJAS"))
    b = clave(normalizar_nombre("JUAN CARLOS GIMENES ROJAS"))
    assert similitud(a, b) > 0.93
    c = clave(normalizar_nombre("PEDRO LUIS FERREIRA SOSA"))
    assert similitud(a, c) < 0.8
