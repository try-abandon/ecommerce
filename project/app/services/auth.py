import jwt
from fastapi import HTTPException, status

from project.app.schemas.user import CurrentUser
from common.config import get_settings


class AuthService:
    """
    认证服务
    """

    def __init__(self):
        self.settings = get_settings()

    def get_authorized_user(self,
                            authorization: str | None,
                            *roles: str
                            ) -> CurrentUser:
        """
        获取当前用户信息以及完成角色的校验
        :return:
        """
        # 1、根据令牌获得用户信息
        current_user = self._get_current_user(authorization)

        # 2、校验角色
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_UNAUTHORIZED,
                detail="用户无访问权限"
            )

        return current_user

    def _get_current_user(self, authorization: str | None) -> CurrentUser:
        # 1、获取令牌
        token = self._obtain_token(authorization)

        # 2、根据令牌解密用户信息
        current_user = self._decode_user_information(token)

        return current_user

    def _obtain_token(self, authorization: str | None) -> str:
        """
        提取令牌
        :return: 令牌
        """
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="该用户未认证"
            )

        return authorization.split(" ", maxsplit=1)[1]

    def _decode_user_information(self, token: str) -> CurrentUser:
        """
        根据令牌解密用户信息
        :return: 当前用户对象
        """
        payload = jwt.decode(token,
                             self.settings.jwt_secret,
                             algorithms=[self.settings.jwt_algorithm]
                             )

        return CurrentUser.model_validate(payload)
