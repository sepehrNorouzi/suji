from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from exceptions.social import AlreadyFriendError
from social.models import FriendshipRequest, Friendship
from social.serializers import FriendshipRequestSerializer, RequestedFriendshipSerializer, FriendshipSerializer


class FriendshipRequestViewSet(GenericViewSet, mixins.ListModelMixin, mixins.DestroyModelMixin,
                               mixins.CreateModelMixin):
    queryset = FriendshipRequest.objects.filter(is_active=True)
    serializer_class = FriendshipRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return self.queryset.filter(receiver=self.request.user)

    def get_requested_friendships(self):
        return self.queryset.filter(sender=self.request.user)

    def get_object(self):
        obj: FriendshipRequest = super(FriendshipRequestViewSet, self).get_object()
        if obj.receiver == self.request.user or obj.sender == self.request.user:
            return obj
        raise Http404

    def get_requested_friendship_object(self) -> FriendshipRequest:
        queryset = self.get_requested_friendships()
        lookup_url_kwarg = 'request_id'
        assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
        )
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        self.check_object_permissions(self.request, obj)

        return obj

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data={**request.data, 'sender_id': self.request.user.id})
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except AlreadyFriendError as e:
            return Response(data={"error": _(str(e))}, status=status.HTTP_409_CONFLICT)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(methods=['GET'], detail=False, url_path='requested', url_name='requested',
            serializer_class=RequestedFriendshipSerializer)
    def requested_friendships(self, request, *args, **kwargs):
        queryset = self.get_requested_friendships()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['DELETE'], detail=False, url_path='requested/(?P<request_id>[0-9]+)',
            url_name='requested-delete', )
    def remove_requested_friendship(self, request, *args, **kwargs):
        requested_friendship = self.get_requested_friendship_object()
        requested_friendship.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['POST'], detail=True, url_path='accept', url_name='accept',
            serializer_class=FriendshipSerializer)
    def accept(self, request, *args, **kwargs):
        friendship_request = self.get_object()
        friendship = friendship_request.accept()
        return Response(data=self.get_serializer(friendship).data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=True, url_path='reject', url_name='reject', )
    def reject(self, request, *args, **kwargs):
        friendship_request = self.get_object()
        friendship_request.reject()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendshipViewSet(GenericViewSet, mixins.ListModelMixin, mixins.DestroyModelMixin):

    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated, ]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return Friendship.list_friends(self.request.user)
