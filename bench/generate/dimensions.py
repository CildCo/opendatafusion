from random import Random

SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜")
GIVEN = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋",
         "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平"]
PROVINCES = ["北京市", "上海市", "广东省", "江苏省", "浙江省", "山东省",
             "河南省", "四川省", "湖北省", "湖南省", "福建省", "安徽省"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉",
          "西安", "苏州", "天津", "重庆", "长沙", "郑州", "青岛", "宁波"]
CATEGORIES = ["手机数码", "家用电器", "服饰鞋包", "美妆个护", "食品生鲜",
              "母婴玩具", "运动户外", "家居家装"]
BRANDS = ["华光", "山海", "云启", "青禾", "星河", "远山", "长风", "万象"]
PRODUCT_WORDS = ["旗舰版", "轻量款", "家庭装", "经典款", "升级版", "便携款",
                 "礼盒装", "专业版", "入门款", "限定款"]


def chinese_name(rng: Random) -> str:
    return rng.choice(SURNAMES) + "".join(
        rng.choice(GIVEN) for _ in range(rng.randint(1, 2)))


def phone(rng: Random) -> str:
    return "1" + rng.choice("3456789") + "".join(
        str(rng.randrange(10)) for _ in range(9))


def address(rng: Random) -> str:
    return (f"{rng.choice(PROVINCES)}{rng.choice(CITIES)}"
            f"市某路{rng.randint(1, 999)}号")


def product_name(rng: Random) -> str:
    return f"{rng.choice(BRANDS)}{rng.choice(CATEGORIES)}{rng.choice(PRODUCT_WORDS)}"
