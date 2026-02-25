class Controparte:
    """
    Small View of the "Controparte" class of Contract Geek
    """

    DEFAULT_PIVA = "00000000000"

    def __init__(
        self,
        controparte_id: int,
        controparte_name: str,
        controparte_piva: str,
        controparte_type: int,  # 0 is Standard, 1 is Natural Person
        controparte_cf: str,
    ):
        self.controparte_id = controparte_id
        self.controparte_name = controparte_name
        self.controparte_type = controparte_type
        self.controparte_piva = controparte_piva
        self.controparte_cf = controparte_cf

    def __init__(self, data: dict):
        self.controparte_id = data["controparte_id"]
        self.controparte_name = data["controparte_name"]
        self.controparte_piva = data["controparte_piva"]
        self.controparte_type = data["controparte_type"]
        self.controparte_cf = data["controparte_cf"]

    def get_dict_key_att(self) -> str:
        if self.controparte_piva == self.DEFAULT_PIVA:
            return self.controparte_cf
        else:
            return self.controparte_piva

    def __repr__(self):
        text = f"Controparte {self.controparte_id} is {self.controparte_name}.\nTheir type is {self.controparte_type} with PIVA {self.controparte_piva} and CF {self.controparte_cf}"
        return text


class ControparteUser:
    id: int
    name: str
    surname: str
    mail: str
    phone: str
    cf: str
    metadata: str

    def __init__(self, data: dict):
        self.id = data["id"]
        self.name = data["name"]
        self.surname = data["surname"]
        self.mail = data["mail"]
        self.phone = data["phone"]
        self.cf = data["cf"]
        self.metadata = data["metadata"]
