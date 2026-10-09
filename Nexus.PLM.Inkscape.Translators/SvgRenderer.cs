using System.IO.Compression;
using SkiaSharp;
using Svg.Skia;

namespace Nexus.PLM.Inkscape.Translators;

/// <summary>
/// Loads an SVG and renders it with Skia — pure .NET, no Inkscape needed on the server, which
/// is what makes these the cheapest proof of the per-add-in translator pattern. Shared by the
/// three translators so the sizing and compression rules exist once.
/// </summary>
internal static class SvgRenderer
{
    /// <summary>Fallback canvas edge when the SVG declares no usable size.</summary>
    private const float DefaultSize = 512f;

    /// <summary>
    /// Loads the document, transparently gunzipping <c>.svgz</c> content (the format catalog
    /// maps both extensions to <c>image/svg+xml</c>, so either may arrive).
    /// </summary>
    /// <exception cref="InvalidOperationException">The bytes are not a renderable SVG.</exception>
    public static SKSvg Load(Stream input)
    {
        using var ms = new MemoryStream();
        input.CopyTo(ms);
        var bytes = ms.ToArray();

        Stream source = bytes is [0x1F, 0x8B, ..]
            ? new GZipStream(new MemoryStream(bytes), CompressionMode.Decompress)
            : new MemoryStream(bytes);

        var svg = new SKSvg();
        try
        {
            using (source) svg.Load(source);
        }
        catch (Exception ex)
        {
            // The XML parser's own error names a line and column of a temp stream - useless in
            // a job log. Say what the translator actually needs.
            throw new InvalidOperationException(
                "The input is not a renderable SVG document. The svg_to_* translators read " +
                "image/svg+xml content (.svg, or gzipped .svgz).", ex);
        }

        if (svg.Picture is null)
            throw new InvalidOperationException("The input is not a renderable SVG document.");
        return svg;
    }

    /// <summary>The document's size, falling back to a square when it declares none.</summary>
    public static SKSize SizeOf(SKSvg svg)
    {
        var rect = svg.Picture!.CullRect;
        return rect.Width > 0 && rect.Height > 0
            ? new SKSize(rect.Width, rect.Height)
            : new SKSize(DefaultSize, DefaultSize);
    }

    /// <summary>Renders to a bitmap. JPEG has no alpha, so callers pass an opaque background
    /// for it; PNG keeps transparency.</summary>
    public static SKBitmap ToBitmap(SKSvg svg, SKColor background)
    {
        var size = SizeOf(svg);
        var bitmap = new SKBitmap((int)Math.Ceiling(size.Width), (int)Math.Ceiling(size.Height));
        using var canvas = new SKCanvas(bitmap);
        canvas.Clear(background);
        canvas.DrawPicture(svg.Picture);
        canvas.Flush();
        return bitmap;
    }
}
