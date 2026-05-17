//引入头部
/* $.ajax({
    type: "GET",
    url: "Comm/header.html",
    dataType: "html",
    async:false,
    success: function(data){
        $("#header").html(data)
    }
});
//引入底部
$.ajax({
    type: "GET",
    url: "Comm/footer.html",
    dataType: "html",
    async:false,
    success: function(data){
        $("#footer").html(data)
    }
}); */
// 移动端导航显示隐藏
var st=0;//滚动条滚动的距离
$(".menu-handle").click(function () {
    $(this).toggleClass("active");
    if($(this).hasClass("active")){
        $(".header .nav").show();
        //防止弹窗打开时底部页面滑动
        st=$(window).scrollTop();
        $("body").css({"position": "fixed", "top": "0", "left": "0", "right": "0", "bottom": "0"});
        $(".language-nav").hide();//关闭语言选择框
        $(".select-language").removeClass("active");
        $(".header").removeClass("open-search");//关闭搜索框
    }else{
        $(".header .nav").hide();
        $("body").attr("style", "");
        $('html,body').stop().animate({'scrollTop': st+ "px"}, 0);
    }
});
// 移动端导航交互
$(".header .nav").on("click",".nav-item>a .icon-more",function () {
    $(this).parent().parent().toggleClass("active");
    return false;
});
// 移动端导航交互
$(".header .product .left-box").on("click","li>a .icon-more",function () {
    $(this).parent().parent("").toggleClass("active");
    return false;
});
// 滚动屏幕时导航变小固定在顶部
$(window).scroll(function() {
    var st = $(window).scrollTop();
    if(st>100){
        $('.header').addClass("top");
    }else{
        $('.header').removeClass("top");
    }
});
//返回顶部  当滚动条的位置处于距顶部100像素以下时，返回顶部按钮出现，否则消失
$(window).scroll(function(){
    if ($(window).scrollTop()>100){
        $(".back-top-menu").fadeIn(100);
    }
    else
    {
        $(".back-top-menu").fadeOut(100);
    }
});
//当点击跳转链接后，回到页面顶部位置
$("#backTop").click(function() {
    $('body,html').animate({scrollTop: 0}, 1000);
    return false;
});

$("#menu-item").on("mousemove",function(){
    $(this).addClass("active")
    $("#menuAll").show()
})
$("#menu-item").on("mouseout",function(){
    $("#menuAll").hide()
    $(this).removeClass("active")
})
// 打开头部搜索框
$(".btn-search").click(function () {
    if(!$(".header").hasClass("open-search")){
        $(".header").addClass("open-search");
        $(".language-nav").hide();//关闭语言选择框
        $(".select-language").removeClass("active");
    }else{
        $(".header").removeClass("open-search")
    }
});
// header中选择语言
$(".select-language").click(function () {
    if(!$(this).hasClass("active")){
        $(this).addClass("active");
        $(this).siblings(".select-nav").show();
        $(".header").removeClass("open-search")//关闭搜索框
    }else{
        $(this).removeClass("active");
        $(this).siblings(".select-nav").hide();
    }
});
// 产品详情页选中语言
$(".select-nav").on("click","li",function () {
    $(".select-language").removeClass("active");
    $(this).parent(".select-nav").hide();
    $(this).parent(".select-nav").siblings(".select-language").children(" input").val($(this).children().text());
});
// 搜索绑定enter键
$(".header .search-box .search-text").bind('keydown',function(event){
    var value=$(this).val();
    var url=$(this).attr('data-url');
    if(event.keyCode == "13") {
        location.href=url+"?search="+value;
    }
});
$(".accordion").on("click",".accordion-toggle",function () {
    if($(this).hasClass("active")){
        $(this).removeClass("active");
        $(this).siblings(".accordion-body").css("height",0);
    }else{
        $(this).addClass("active");
        $(this).siblings(".accordion-body").css("height",$(this).siblings(".accordion-body").children(".content").height());
    }

});