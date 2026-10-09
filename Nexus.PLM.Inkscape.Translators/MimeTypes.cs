namespace Nexus.PLM.Inkscape.Translators;

/// <summary>
/// The MIME values this repo's translators speak. Values follow the installation's format
/// catalog (the MIME Types app), which is the source of truth for format names — the SVG row
/// there maps both <c>.svg</c> and <c>.svgz</c> to one value, which is why the renderer
/// gunzips transparently.
/// </summary>
public static class MimeTypes
{
    /// <summary>Inkscape drawing (<c>.svg</c>/<c>.svgz</c>) — this repo's input format.</summary>
    public const string Svg = "image/svg+xml";

    /// <summary>PNG raster.</summary>
    public const string Png = "image/png";

    /// <summary>JPEG raster.</summary>
    public const string Jpeg = "image/jpeg";

    /// <summary>PDF.</summary>
    public const string Pdf = "application/pdf";
}
