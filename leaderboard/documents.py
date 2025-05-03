from mongoengine import StringField, EmbeddedDocument, EmbeddedDocumentField, Document, DateTimeField, IntField, \
    ListField


class LeaderboardResultDocument(EmbeddedDocument):
    id = IntField()
    profile_name = StringField(default=None)
    avatar = IntField(default=None)
    username = StringField()
    score = IntField()
    rank = IntField()


class LeaderboardDocument(Document):
    name = StringField(required=True, max_length=100)
    archive_time = DateTimeField()
    key = StringField(required=True, max_length=100)
    results = ListField(EmbeddedDocumentField(LeaderboardResultDocument))
