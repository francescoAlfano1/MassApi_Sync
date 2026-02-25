from dataclasses import dataclass, field
from typing import List, Optional
from classes.Data import SignBoxPlaceholder
import uuid
import json


@dataclass
class BaseBox:
    field_id: str
    user: int
    page: int
    x: int
    y: int
    width: int
    height: int
    rotation_degree: int


@dataclass
class SignBox(BaseBox):
    page_height: int


@dataclass
class TextArea(BaseBox):
    areaType: int
    text: str
    userId: int
    question: str
    fontFamily: int
    fontSize: int
    color: str
    isBold: bool
    isItalic: bool
    required: bool


@dataclass
class CheckBox(BaseBox):
    is_checked: bool
    required: bool
    group_id: str


@dataclass
class OptionBox(BaseBox):
    is_checked: bool
    required: bool
    group_id: str


@dataclass
class WorkflowDocument:
    document_id: int
    filename: str = ""
    signBoxes: List[SignBox] = field(default_factory=list)
    textAreas: List[TextArea] = field(default_factory=list)
    checkBoxes: List[CheckBox] = field(default_factory=list)
    optionBoxes: List[OptionBox] = field(default_factory=list)
    document_type: int = 0

    def __init__(self, data: dict):
        self.document_id = data["document_id"]
        self.filename = data.get("filename", "")
        self.signBoxes = [SignBox(**signbox) for signbox in data.get("signBoxes", [])]
        self.textAreas = [
            TextArea(**text_area) for text_area in data.get("textAreas", [])
        ]
        self.checkBoxes = [
            CheckBox(**check_box) for check_box in data.get("checkBoxes", [])
        ]
        self.optionBoxes = [
            OptionBox(**option_box) for option_box in data.get("optionBoxes", [])
        ]
        self.document_type = data.get("document_type", 0)


@dataclass
class Contributor:
    contributor_uuid: str
    users: List[int] = field(default_factory=list)
    doc_description: str = ""
    required: bool = False


@dataclass
class Workflow:
    workflow_id: int
    controparte_id: int
    status_id: int
    approvers: List[int] = field(default_factory=list)
    sequential_approval: bool = False
    signers: List[int] = field(default_factory=list)
    sequential_sign: bool = False
    contributors: List[Contributor] = field(default_factory=list)
    sign_option_id: int = 0
    temp_link_delta_days_expire: int = 0
    workflow_documents: List[WorkflowDocument] = field(default_factory=list)

    def __init__(self, data: dict):
        self.workflow_id = data["workflow_id"]
        self.controparte_id = data["controparte_id"]
        self.status_id = data["status_id"]
        self.approvers = data.get("approvers", [])
        self.sequential_approval = data.get("sequential_approval", False)
        self.signers = data.get("signers", [])
        self.sequential_sign = data.get("sequential_sign", False)
        self.contributors = [
            Contributor(contributor) for contributor in data.get("contributors", [])
        ]
        self.sign_option_id = data.get("sign_option_id", 0)
        self.temp_link_delta_days_expire = data.get("temp_link_delta_days_expire", 0)
        self.workflow_documents = [
            WorkflowDocument(doc) for doc in data.get("workflow_documents", [])
        ]

    def add_approver(self, approver_id: int):
        if approver_id not in self.approvers:
            self.approvers.append(approver_id)

    def add_signbox(
        self,
        document_id: int,
        user: int,
        page: int,
        x: int,
        y: int,
        width: int,
        height: int,
    ):
        """
        Adds a SignBox to a specific document and updates the list of signers.

        Args:
            document_id (int): The ID of the document to which the SignBox will be added.
            user (int): The user ID associated with the SignBox.
            page (int): The page number where the SignBox will be placed.
            x (int): The x-coordinate of the SignBox.
            y (int): The y-coordinate of the SignBox.
            width (int): The width of the SignBox.
            height (int): The height of the SignBox.

        Raises:
            ValueError: If the document with the given ID is not found.
        """
        # Find the corresponding document
        document = next(
            (doc for doc in self.workflow_documents if doc.document_id == document_id),
            None,
        )
        if not document:
            raise ValueError(f"Document with ID {document_id} not found.")

        # Create the SignBox and add it to the document
        signbox = SignBox(
            field_id=str(uuid.uuid4()),
            user=user,
            page=page,
            x=x,
            y=y,
            width=width,
            height=height,
            rotation_degree=0,  # Default value
            page_height=0,  # Default value
        )
        document.signBoxes.append(signbox)

        # Add the user ID to signers if not already present
        if user not in self.signers:
            self.signers.append(user)

    def add_signbox_from_placeholder(
        self, document_id: int, user: int, page: int, signbox: SignBoxPlaceholder
    ):
        self.add_signbox(
            document_id, user, page, signbox.x, signbox.y, signbox.width, signbox.height
        )

    def to_json(self) -> str:
        """
        Converts the Workflow object to a JSON string.

        Returns:
            str: JSON representation of the Workflow object.
        """
        return json.dumps(self, default=lambda o: o.__dict__, indent=None)

    def __repr__(self):
        return (
            f"Workflow {self.workflow_id} with status {self.status_id}.\n"
            f"Controparte ID: {self.controparte_id}, Approvers: {self.approvers}, "
            f"Signers: {self.signers}, Sequential Approval: {self.sequential_approval}, "
            f"Sequential Sign: {self.sequential_sign}, Contributors: {self.contributors}, "
            f"Documents: {len(self.workflow_documents)}"
        )
